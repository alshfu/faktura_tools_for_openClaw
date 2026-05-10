#!/usr/bin/env python3
"""
delete_invoice.py — Soft-delete av faktura.

Sätter status=borttagen men behåller all data för audit.
PDF-filen tas INTE bort från disk.

Användning:
  python3 delete_invoice.py --faktura-id {id} --skal "..."
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

PROJEKT_ROT = Path(__file__).resolve().parent.parent.parent
DB_TOOLS    = PROJEKT_ROT / "tools" / "db"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--faktura-id", required=True, dest="faktura_id")
    p.add_argument("--skal",       default="Ingen anledning angiven")
    args = p.parse_args()

    r = subprocess.run([
        "python3", str(DB_TOOLS / "db_invoices.py"),
        "--ta-bort", args.faktura_id,
        "--skal",    args.skal,
    ], capture_output=True, text=True)

    print(r.stdout)
    sys.exit(0 if r.returncode == 0 else 1)


if __name__ == "__main__":
    main()
