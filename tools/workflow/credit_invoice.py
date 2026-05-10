#!/usr/bin/env python3
"""
credit_invoice.py — Skapar och skickar kreditnota för befintlig faktura.

Flöde:
1. db_invoices.py --kreditera {original_id}  → ny faktura med doc_type=kreditnota
2. create_invoice.py --faktura-id {kredit_id}  → PDF
3. send_invoice.py --faktura-id {kredit_id} --till {tel}  → till WhatsApp

Användning:
  python3 credit_invoice.py --original-id {id} --skal "..." --till {tel}
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

PROJEKT_ROT = Path(__file__).resolve().parent.parent.parent
DB_TOOLS    = PROJEKT_ROT / "tools" / "db"
WORKFLOW    = PROJEKT_ROT / "tools" / "workflow"


def kor(cmd: list, timeout: int = 60) -> dict:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    try:
        return json.loads(r.stdout)
    except Exception:
        return {"status": "fel", "meddelande": r.stderr or r.stdout}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--original-id", required=True, dest="original_id")
    p.add_argument("--skal",        default="Kreditering")
    p.add_argument("--till",        help="Skicka PDF till detta WhatsApp-nummer")
    args = p.parse_args()

    # 1. Kreditera i DB
    kredit = kor([
        "python3", str(DB_TOOLS / "db_invoices.py"),
        "--kreditera", args.original_id,
        "--skal",      args.skal,
    ])
    if kredit.get("status") != "ok":
        print(json.dumps(kredit, ensure_ascii=False)); sys.exit(1)

    kredit_id = kredit["kredit_faktura_id"]

    # 2. Skapa PDF
    pdf = kor([
        "python3", str(WORKFLOW / "create_invoice.py"),
        "--faktura-id", kredit_id,
    ])
    if pdf.get("status") != "ok":
        print(json.dumps({
            "status":         "delvis_ok",
            "kredit_id":      kredit_id,
            "kredit_nummer":  kredit["kredit_nummer"],
            "pdf_fel":        pdf.get("meddelande"),
        }, ensure_ascii=False))
        sys.exit(1)

    # 3. Skicka till WhatsApp om angiven
    if args.till:
        skick = kor([
            "python3", str(WORKFLOW / "send_invoice.py"),
            "--faktura-id", kredit_id,
            "--till",       args.till,
        ])
        if skick.get("status") != "ok":
            print(json.dumps({
                "status":         "delvis_ok",
                "kredit_id":      kredit_id,
                "kredit_nummer":  kredit["kredit_nummer"],
                "pdf_sokväg":     pdf.get("pdf_sokväg"),
                "skicka_fel":     skick.get("meddelande"),
            }, ensure_ascii=False))
            sys.exit(1)

    print(json.dumps({
        "status":         "ok",
        "kredit_id":      kredit_id,
        "kredit_nummer":  kredit["kredit_nummer"],
        "original_id":    args.original_id,
        "pdf_sokväg":     pdf.get("pdf_sokväg"),
        "att_kreditera":  kredit.get("att_kreditera"),
        "skickad_till":   args.till if args.till else None,
        "skal":           args.skal,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
