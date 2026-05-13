#!/usr/bin/env python3
"""db_messages.py — CRUD för meddelandelogg.

Lagrar inkommande och utgående WhatsApp-meddelanden i data/messages.json.
Användning:

  # Logga ett inkommande meddelande
  python3 db_messages.py --logga-in \
    --telefon "+46735272989" \
    --text "Hej, vill du fakturera idag?"

  # Logga ett utgående meddelande
  python3 db_messages.py --logga-ut \
    --telefon "+46735272989" \
    --text "Ja, vad ska faktureras?" \
    --mall "common/greeting.txt"

  # Lista meddelanden för en kontakt
  python3 db_messages.py --lista --telefon "+46735272989" --sedan "7d" --max 50

  # Lista aktiva klienter senaste N dagar
  python3 db_messages.py --aktiva --sedan "7d"

  # JSON-utdata för alla operationer (för programmatisk användning från andra skript).

Schema (version 1):
{
  "version": 1,
  "messages": [
    {
      "id": "msg_<timestamp>_<random>",
      "tidpunkt": "2026-05-13T17:04:00+02:00",
      "riktning": "in" | "ut",
      "telefon": "+46735272989",
      "text": "...",
      "mall": "common/greeting.txt" | null,
      "media": null | {"typ": "pdf", "url": "..."},
      "agent": "fyodor"
    }
  ]
}

Telefonnummer normaliseras alltid till E.164-format (+landskod...).
"""

import argparse
import json
import os
import re
import secrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Standardplats för data-katalogen. Kan överstyras med env BILLING_DATA_DIR.
DATA_DIR = Path(os.environ.get("BILLING_DATA_DIR", Path.home() / "billing-system" / "data"))
MESSAGES_PATH = DATA_DIR / "messages.json"
SCHEMA_VERSION = 1


def _ensure_storage() -> None:
    """Skapar data-katalog och tom messages.json om de saknas."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not MESSAGES_PATH.exists():
        MESSAGES_PATH.write_text(
            json.dumps({"version": SCHEMA_VERSION, "messages": []}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _load() -> dict:
    _ensure_storage()
    with MESSAGES_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict) -> None:
    # Atomär skrivning via temp-fil + rename — undviker korruption vid crash.
    tmp = MESSAGES_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(MESSAGES_PATH)


def normalisera_telefon(raw: str) -> str:
    """Normaliserar telefonnummer till E.164-format.

    Hanterar:
      +79956326096 → +79956326096
      79956326096  → +79956326096
      89956326096  → +79956326096 (RU: 8-prefix → +7)
      +7 (995) 632-60-96 → +79956326096
      0735272989 → ej entydigt, returneras som +46735272989 antagande SE
    """
    if not raw:
        return ""
    s = re.sub(r"[\s\-\(\)]", "", raw.strip())
    if s.startswith("+"):
        return s
    if s.startswith("00"):
        return "+" + s[2:]
    if s.startswith("8") and len(s) == 11:
        # Ryskt 8-prefix → +7
        return "+7" + s[1:]
    if s.startswith("0") and len(s) >= 9:
        # Svenskt 0-prefix → +46
        return "+46" + s[1:]
    # Antar att det redan är landskod utan +
    return "+" + s


def _parse_sedan(sedan: str) -> datetime:
    """Tolkar '7d', '24h', '2026-05-01' eller ISO-datetime till UTC datetime."""
    if not sedan:
        # Default: 7 dagar bakåt
        return datetime.now(timezone.utc) - timedelta(days=7)
    sedan = sedan.strip().lower()
    m = re.match(r"^(\d+)\s*([dhm])$", sedan)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        delta = {"d": timedelta(days=n), "h": timedelta(hours=n), "m": timedelta(minutes=n)}[unit]
        return datetime.now(timezone.utc) - delta
    # ISO-datum eller datetime
    try:
        if "t" in sedan:
            return datetime.fromisoformat(sedan).astimezone(timezone.utc)
        return datetime.fromisoformat(sedan).replace(tzinfo=timezone.utc)
    except ValueError:
        raise SystemExit(f"FEL: kan inte tolka '{sedan}' — använd '7d', '24h' eller ISO-datum.")


def _gen_id() -> str:
    return f"msg_{int(datetime.now(timezone.utc).timestamp())}_{secrets.token_hex(3)}"


def logga(riktning: str, telefon: str, text: str, mall: str | None = None, media: dict | None = None) -> dict:
    if riktning not in ("in", "ut"):
        raise SystemExit("FEL: --riktning måste vara 'in' eller 'ut'")
    data = _load()
    entry = {
        "id": _gen_id(),
        "tidpunkt": datetime.now(timezone.utc).isoformat(),
        "riktning": riktning,
        "telefon": normalisera_telefon(telefon),
        "text": text or "",
        "mall": mall,
        "media": media,
        "agent": "fyodor",
    }
    data["messages"].append(entry)
    _save(data)
    return entry


def lista(telefon: str | None, sedan: str | None, till: str | None, max_n: int) -> list[dict]:
    data = _load()
    msgs = data.get("messages", [])
    if telefon:
        norm = normalisera_telefon(telefon)
        msgs = [m for m in msgs if m.get("telefon") == norm]
    threshold_start = _parse_sedan(sedan)
    msgs = [m for m in msgs if datetime.fromisoformat(m["tidpunkt"]) >= threshold_start]
    if till:
        threshold_end = _parse_sedan(till)
        msgs = [m for m in msgs if datetime.fromisoformat(m["tidpunkt"]) <= threshold_end]
    # Senaste sist (kronologiskt)
    msgs.sort(key=lambda m: m["tidpunkt"])
    if max_n > 0:
        msgs = msgs[-max_n:]
    return msgs


def aktiva_klienter(sedan: str | None) -> list[dict]:
    """Returnerar lista över unika telefonnummer med antal meddelanden i intervallet."""
    msgs = lista(telefon=None, sedan=sedan, till=None, max_n=0)
    bucket: dict[str, dict] = {}
    for m in msgs:
        tel = m["telefon"]
        if tel not in bucket:
            bucket[tel] = {"telefon": tel, "antal_in": 0, "antal_ut": 0, "senast": m["tidpunkt"]}
        if m["riktning"] == "in":
            bucket[tel]["antal_in"] += 1
        else:
            bucket[tel]["antal_ut"] += 1
        if m["tidpunkt"] > bucket[tel]["senast"]:
            bucket[tel]["senast"] = m["tidpunkt"]
    return sorted(bucket.values(), key=lambda x: x["senast"], reverse=True)


def main():
    p = argparse.ArgumentParser(description="Meddelandelogg CRUD")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--logga-in", action="store_true", help="Logga inkommande meddelande")
    g.add_argument("--logga-ut", action="store_true", help="Logga utgående meddelande")
    g.add_argument("--lista", action="store_true", help="Lista meddelanden")
    g.add_argument("--aktiva", action="store_true", help="Lista aktiva klienter")

    p.add_argument("--telefon", help="Telefonnummer (E.164 eller tolerant)")
    p.add_argument("--text", help="Meddelandetext", default="")
    p.add_argument("--mall", help="Mallnamn (för utgående)", default=None)
    p.add_argument("--media", help="JSON-sträng för media", default=None)
    p.add_argument("--sedan", help="Tidsintervall: '7d', '24h' eller ISO-datum", default=None)
    p.add_argument("--till", help="Slutdatum", default=None)
    p.add_argument("--max", type=int, default=100, help="Max antal meddelanden")

    args = p.parse_args()

    try:
        if args.logga_in or args.logga_ut:
            if not args.telefon:
                raise SystemExit("FEL: --telefon krävs vid loggning")
            riktning = "in" if args.logga_in else "ut"
            media = json.loads(args.media) if args.media else None
            entry = logga(riktning, args.telefon, args.text, args.mall, media)
            print(json.dumps({"ok": True, "meddelande": entry}, ensure_ascii=False, indent=2))

        elif args.lista:
            msgs = lista(args.telefon, args.sedan, args.till, args.max)
            print(json.dumps({"ok": True, "antal": len(msgs), "meddelanden": msgs}, ensure_ascii=False, indent=2))

        elif args.aktiva:
            klienter = aktiva_klienter(args.sedan)
            print(json.dumps({"ok": True, "antal": len(klienter), "klienter": klienter}, ensure_ascii=False, indent=2))

    except SystemExit:
        raise
    except Exception as e:
        print(json.dumps({"ok": False, "fel": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
