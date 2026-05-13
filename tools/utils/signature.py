#!/usr/bin/env python3
"""signature.py — bestämmer korrekt Fjodor-signatur per mottagare.

Importeras av send_template.py för att automatiskt lägga till signatur
före varje utgående meddelande. Detta säkerställer att klienter alltid ser
att det är boten som skriver, inte en människa.

Användning från send_template.py:

    from utils.signature import prepend_signature
    final_text = prepend_signature(rendered_text, recipient_phone=args.till)
    # ...skicka final_text via gateway

Eller från CLI för test:
    python3 signature.py --till "+46735272989" --text "Hej!"
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

PROJEKT_ROT = Path(os.environ.get("BILLING_ROOT", Path.home() / "billing-system"))
DB_PHONE_MAP = PROJEKT_ROT / "tools" / "db" / "db_phone_map.py"
DB_RECIPIENTS = PROJEKT_ROT / "tools" / "db" / "db_recipients.py"

SIGNATURES = {
    "sv": "Det är Fjodor som skriver.",
    "ru": "Вам пишет Фёдор.",
    "en": "This is Fjodor.",
    "fi": "Tämä on Fjodor.",
    "no": "Det er Fjodor som skriver.",
    "da": "Det er Fjodor, der skriver.",
}
DEFAULT_SIGNATURE = SIGNATURES["sv"]

HUVUDAGARE = "+79956326096"


def normalisera_telefon(raw: str) -> str:
    if not raw:
        return ""
    s = re.sub(r"[\s\-\(\)]", "", raw.strip())
    if s.startswith("+"):
        return s
    if s.startswith("00"):
        return "+" + s[2:]
    if s.startswith("8") and len(s) == 11:
        return "+7" + s[1:]
    if s.startswith("0") and len(s) >= 9:
        return "+46" + s[1:]
    return "+" + s


def _kor_tyst(cmd: list[str]) -> dict | None:
    """Kör ett underskript och returnerar tolkad JSON, eller None vid fel."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            return json.loads(r.stdout)
    except Exception:
        pass
    return None


def bestam_sprak(telefon: str) -> str:
    """Hämtar mottagarens språkpreferens.

    Strategi:
      1. Om telefon == HUVUDAGARE → 'ru' (ägaren skriver på ryska som default).
      2. Om telefon finns i phone_map med sprak-fält → använd det.
      3. Om telefon finns i recipients med sprak-fält → använd det.
      4. Annars 'sv' (svenska som default).
    """
    telefon = normalisera_telefon(telefon)
    if telefon == HUVUDAGARE:
        return "ru"

    # Försök phone_map
    r = _kor_tyst(["python3", str(DB_PHONE_MAP), "--sok", telefon])
    if r and r.get("ok") and r.get("entry"):
        sprak_lista = r["entry"].get("sprak") or []
        if sprak_lista:
            return _normalisera_sprak(sprak_lista[0])

    # Försök recipients
    r = _kor_tyst(["python3", str(DB_RECIPIENTS), "--sok-telefon", telefon])
    if r and r.get("ok"):
        mot = r.get("mottagare") or []
        if mot and mot[0].get("sprak"):
            return _normalisera_sprak(mot[0]["sprak"])

    return "sv"


def _normalisera_sprak(s: str) -> str:
    s = (s or "").strip().lower()
    karta = {
        "svenska": "sv", "swedish": "sv", "sv": "sv", "se": "sv",
        "ryska": "ru", "russian": "ru", "ru": "ru", "русский": "ru",
        "engelska": "en", "english": "en", "en": "en",
        "finska": "fi", "finnish": "fi", "fi": "fi",
        "norska": "no", "norwegian": "no", "no": "no",
        "danska": "da", "danish": "da", "da": "da",
    }
    return karta.get(s, "sv")


def hamta_signatur(telefon: str) -> str:
    return SIGNATURES.get(bestam_sprak(telefon), DEFAULT_SIGNATURE)


def prepend_signature(text: str, recipient_phone: str) -> str:
    """Lägger till signatur först i texten om den inte redan finns.

    Idempotent — om signaturen redan står först (på något språk) görs inget.
    """
    if not text:
        return text
    signatur = hamta_signatur(recipient_phone)
    forsta_rad = text.strip().splitlines()[0] if text.strip() else ""
    # Om någon av de kända signaturerna redan står först — gör inget.
    if any(forsta_rad.strip().startswith(s) for s in SIGNATURES.values()):
        return text
    return f"{signatur}\n\n{text.lstrip()}"


def main():
    p = argparse.ArgumentParser(description="Lägg till Fjodor-signatur i text")
    p.add_argument("--till", required=True, help="Mottagarens telefon")
    p.add_argument("--text", required=True, help="Text att signera")
    args = p.parse_args()
    print(prepend_signature(args.text, args.till))


if __name__ == "__main__":
    main()
