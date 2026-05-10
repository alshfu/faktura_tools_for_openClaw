#!/usr/bin/env python3
"""
identify_sender.py — FÖRSTA steget vid varje inkommande meddelande.

Slår upp telefonnumret i phone_map.json och returnerar:
- Vem är avsändaren? (anställd/ägare/okänd)
- Vilket bolag arbetar de för?
- Vilka begränsningar gäller?

Användning:
  python3 identify_sender.py --telefon +46735272989
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

PROJEKT_ROT = Path(__file__).resolve().parent.parent.parent
DB_TOOLS    = PROJEKT_ROT / "tools" / "db"


def kor(cmd: list) -> dict:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return json.loads(r.stdout) if r.stdout else {"status": "fel"}
    except Exception as e:
        return {"status": "fel", "meddelande": str(e)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--telefon", required=True)
    args = p.parse_args()

    # 1. Slå upp telefon → koppling
    phone_data = kor([
        "python3", str(DB_TOOLS / "db_phone_map.py"),
        "--slag-upp", args.telefon
    ])

    if phone_data.get("status") != "ok":
        print(json.dumps({"status": "fel", "meddelande": "Phone lookup misslyckades"},
                         ensure_ascii=False))
        sys.exit(1)

    avsandare_id = phone_data.get("avsandare_id")
    result = {
        "status":         "ok",
        "telefon":        args.telefon,
        "kanlig":         phone_data.get("kanlig", False),
        "roll":           phone_data.get("roll", "okand"),
        "namn":           phone_data.get("namn", ""),
        "avsandare_id":   avsandare_id,
        "begransningar":  phone_data.get("begransningar", {}),
    }

    # 2. Om kopplad till en avsändare → hämta info om bolaget
    if avsandare_id:
        avs_data = kor([
            "python3", str(DB_TOOLS / "db_senders.py"),
            "--hamta", avsandare_id
        ])
        if avs_data.get("status") == "ok":
            avs = avs_data.get("avsandare", {})
            result["avsandare_namn"]    = avs.get("foretag", {}).get("namn", "")
            result["avsandare_aktiv"]   = avs.get("aktiv", True)
            result["nasta_fakturanr"]   = avs.get("fakturering", {}).get("nasta_faktura_nummer")
            result["design_shablon"]    = avs.get("design", {}).get("shablon_id", "klassisk_svart")

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
