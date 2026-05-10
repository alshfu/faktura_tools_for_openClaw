#!/usr/bin/env python3
"""
send_invoice.py — Skicka PDF till WhatsApp och uppdatera status.

Förutsätter att fakturan redan är skapad (PDF finns på disk).
Använd create_invoice.py först om PDF saknas.

Användning:
  python3 send_invoice.py --faktura-id {id} --till {telefon}
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJEKT_ROT = Path(__file__).resolve().parent.parent.parent
DB_TOOLS    = PROJEKT_ROT / "tools" / "db"


def nu_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def kor(cmd: list) -> dict:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    try:
        return json.loads(r.stdout)
    except Exception:
        return {"status": "fel", "meddelande": r.stderr or r.stdout}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--faktura-id", required=True, dest="faktura_id")
    p.add_argument("--till",       required=True, help="WhatsApp-nummer")
    args = p.parse_args()

    # 1. Hämta fakturan
    fakt = kor(["python3", str(DB_TOOLS / "db_invoices.py"), "--hamta", args.faktura_id])
    if fakt.get("status") != "ok":
        print(json.dumps(fakt, ensure_ascii=False)); sys.exit(1)
    f = fakt["faktura"]

    pdf_path = f.get("pdf", {}).get("sokväg")
    if not pdf_path or not Path(pdf_path).exists():
        print(json.dumps({
            "status": "fel",
            "meddelande": "PDF saknas — kör create_invoice.py först"
        }, ensure_ascii=False))
        sys.exit(1)

    nummer   = f.get("nummer")
    doc_type = f.get("doc_type", "faktura")
    titel    = "Kreditnota" if doc_type == "kreditnota" else "Faktura"
    caption  = f"📄 {titel} nr {nummer}"

    # 2. Skicka via OpenClaw CLI
    r = subprocess.run([
        "openclaw", "message", "send",
        "--channel", "whatsapp",
        "--target",  args.till,
        "--media",   pdf_path,
        "--message", caption,
    ], capture_output=True, text=True, timeout=30)

    skickad = r.returncode == 0 and "Sent via gateway" in r.stdout

    # 3. Logga skickning i DB
    if skickad:
        skickning_info = {
            "metod":         "whatsapp_direkt",
            "skickad_datum": nu_iso(),
            "mottagare_whatsapp": args.till,
        }
        kor([
            "python3", str(DB_TOOLS / "db_invoices.py"),
            "--markera-skickad", args.faktura_id,
            json.dumps(skickning_info, ensure_ascii=False)
        ])

        msg_id = ""
        for tok in r.stdout.split():
            if tok.startswith("3EB") or tok.startswith("3AD"):
                msg_id = tok.rstrip(".")
                break

        print(json.dumps({
            "status":     "ok",
            "faktura_id": args.faktura_id,
            "nummer":     nummer,
            "skickad_till": args.till,
            "pdf":        pdf_path,
            "message_id": msg_id,
        }, ensure_ascii=False))
    else:
        print(json.dumps({
            "status":     "fel",
            "meddelande": (r.stderr or r.stdout)[:300],
            "faktura_id": args.faktura_id,
        }, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
