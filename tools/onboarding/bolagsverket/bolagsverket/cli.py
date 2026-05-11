"""
bolagsverket.cli
----------------
CLI-интерфейс — тонкая обёртка над клиентами библиотеки.

Использование:
    python -m bolagsverket <orgnr> [опции]
    bolagsverket-cli <orgnr> [опции]

Источники данных:
    --source bolagsverket  официальный API (нужны ключи)
    --source mackan        mackan.eu без ключей
    --source auto          автовыбор (по умолчанию)
"""

import argparse
import json
import os
import sys

from .exceptions import BolagsverketError
from .factory import get_client
from .validators import is_valid, legal_form_hint


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="bolagsverket-cli",
        description="Получение данных о шведской компании",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  # Без ключей (через mackan.eu)
  bolagsverket-cli 5560000001 --source mackan --pretty

  # С ключами (официальный API)
  bolagsverket-cli 5560000001 --source bolagsverket --docs --pretty

  # Автовыбор (читает BV_CLIENT_ID/BV_CLIENT_SECRET из env)
  bolagsverket-cli 5560000001 --pretty

  # Сохранить в файл
  bolagsverket-cli 5560000001 --out result.json

  # Только валидация org.nr
  bolagsverket-cli --validate 5560000001

Переменные окружения:
  BV_CLIENT_ID      — OAuth2 client_id
  BV_CLIENT_SECRET  — OAuth2 client_secret
        """,
    )

    p.add_argument("orgnr", nargs="?",
                   help="Organisationsnummer (10 цифр, дефис допустим)")

    p.add_argument("--source", choices=["auto", "bolagsverket", "mackan"],
                   default="auto",
                   help="Источник данных (по умолчанию: auto)")
    p.add_argument("--docs", action="store_true",
                   help="Включить список годовых отчётов")
    p.add_argument("--pretty", action="store_true",
                   help="Форматированный JSON-вывод")
    p.add_argument("--no-raw", action="store_true",
                   help="Не включать raw_api_response")
    p.add_argument("--out", metavar="FILE",
                   help="Сохранить результат в файл")
    p.add_argument("--validate", action="store_true",
                   help="Только проверить org.nr без API-запроса")
    p.add_argument("--client-id",     default=os.getenv("BV_CLIENT_ID"),
                   metavar="ID",      help="OAuth2 client_id")
    p.add_argument("--client-secret", default=os.getenv("BV_CLIENT_SECRET"),
                   metavar="SECRET",  help="OAuth2 client_secret")
    p.add_argument("--timeout", type=int, default=15, metavar="SEC",
                   help="Таймаут HTTP-запросов (по умолчанию: 15)")

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not args.orgnr:
        parser.print_help()
        sys.exit(0)

    # ── Режим валидации ───────────────────────
    if args.validate:
        valid = is_valid(args.orgnr)
        hint = legal_form_hint(args.orgnr)
        status = "✓ корректный" if valid else "✗ некорректный"
        print(f"{status} organisationsnummer: {args.orgnr}")
        print(f"Вероятная правовая форма: {hint}")
        sys.exit(0 if valid else 1)

    # ── Создаём клиент ────────────────────────
    try:
        client = get_client(
            source=args.source,
            client_id=args.client_id,
            client_secret=args.client_secret,
            timeout=args.timeout,
        )
    except ValueError as exc:
        _err(str(exc))

    source_label = getattr(client, "source_name", args.source)
    _log(f"[→] Источник: {source_label}")
    _log(f"[→] Запрашиваем org.nr {args.orgnr}...")

    # ── Запрос ────────────────────────────────
    try:
        company = client.get_company(args.orgnr, include_docs=args.docs)
    except BolagsverketError as exc:
        _err(str(exc))

    # ── Вывод ─────────────────────────────────
    result = company.to_dict(include_raw=not args.no_raw)
    indent = 2 if args.pretty else None
    output = json.dumps(result, ensure_ascii=False, indent=indent)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(output)
        _log(f"[✓] Сохранено в {args.out}")
    else:
        print(output)


def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


def _err(msg: str) -> None:
    print(f"ОШИБКА: {msg}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()

