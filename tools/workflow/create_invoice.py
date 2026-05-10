#!/usr/bin/env python3
"""
create_invoice.py — Generera PDF genom Faktura Constructor (HTTP).

1. Hämtar fakturadata + avsändare + mottagare från databaserna
2. Mappar till Faktura Constructor schema
3. POST → http://localhost:3030/pdf
4. Sparar PDF till diskens fakturaarkiv
5. Uppdaterar invoices.json med PDF-sökväg och status

Användning:
  python3 create_invoice.py --faktura-id {id}
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import requests

PROJEKT_ROT = Path(__file__).resolve().parent.parent.parent
DB_TOOLS    = PROJEKT_ROT / "tools" / "db"

sys.path.insert(0, str(PROJEKT_ROT / "tools"))
from utils.faktura_mapper import mappa


FAKTURA_SERVICE_URL = "http://localhost:3030"
PDF_TIMEOUT_SEC     = 60
FAKTURA_DIR         = Path("/home/administrator/documents/invoices")


def safe_name(s: str) -> str:
    return re.sub(r'[/&\\:*?"<>|]', '-', s).strip()


def kor(cmd: list) -> dict:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    try:
        return json.loads(r.stdout)
    except Exception:
        return {"status": "fel", "meddelande": r.stderr or r.stdout}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--faktura-id", required=True, dest="faktura_id")
    args = p.parse_args()

    # 1. Ladda fakturadata
    fakt = kor(["python3", str(DB_TOOLS / "db_invoices.py"), "--hamta", args.faktura_id])
    if fakt.get("status") != "ok":
        print(json.dumps(fakt, ensure_ascii=False)); sys.exit(1)
    f = fakt["faktura"]

    avs = kor(["python3", str(DB_TOOLS / "db_senders.py"), "--hamta", f["avsandare_id"]])
    if avs.get("status") != "ok":
        print(json.dumps(avs, ensure_ascii=False)); sys.exit(1)

    mot = kor(["python3", str(DB_TOOLS / "db_recipients.py"), "--hamta", f["mottagare_id"]])
    if mot.get("status") != "ok":
        print(json.dumps(mot, ensure_ascii=False)); sys.exit(1)

    # 2. Bygg internt dokument för mappern
    internt_doc = {
        "avsandare":      avs["avsandare"],
        "mottagare":      mot["mottagare"],
        "faktura_info":   {
            "betalningsvillkor_dagar": f.get("datum", {}).get("betalningsvillkor_dagar", 30),
            "faktura_datum":           f.get("datum", {}).get("faktura"),
            "forfallo_datum":          f.get("datum", {}).get("forfallo"),
            "referens":                f.get("meta", {}).get("referens", ""),
            "momslage":                f.get("meta", {}).get("momslage", ""),
            "ocr":                     f.get("meta", {}).get("ocr"),
        },
        "rader":          f.get("rader", []),
        "nummer":         f.get("nummer"),
        "doc_type":       f.get("doc_type", "faktura"),
        "design_shablon": f.get("pdf", {}).get("design_shablon", "klassisk_svart"),
    }

    # 3. Mappa till Faktura Constructor schema
    fc_doc = mappa(internt_doc)

    # 4. Anropa PDF-tjänsten
    try:
        r = requests.post(f"{FAKTURA_SERVICE_URL}/pdf", json=fc_doc, timeout=PDF_TIMEOUT_SEC)
    except requests.exceptions.ConnectionError:
        print(json.dumps({
            "status": "fel",
            "meddelande": f"Kan inte ansluta till Faktura Service på {FAKTURA_SERVICE_URL}"
        }, ensure_ascii=False))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"status": "fel", "meddelande": f"HTTP-fel: {e}"},
                         ensure_ascii=False))
        sys.exit(1)

    if r.status_code != 200:
        print(json.dumps({
            "status": "fel",
            "meddelande": f"Faktura Service HTTP {r.status_code}: {r.text[:300]}"
        }, ensure_ascii=False))
        sys.exit(1)

    # 5. Spara PDF
    avs_namn  = safe_name(avs["avsandare"]["foretag"]["namn"])
    mot_namn  = safe_name(mot["mottagare"]["foretag"]["namn"])
    nummer    = f["nummer"]
    doc_type  = f.get("doc_type", "faktura")
    prefix    = "kreditnota" if doc_type == "kreditnota" else "faktura"

    foretag_dir = FAKTURA_DIR / avs_namn
    foretag_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = foretag_dir / f"{prefix}_{nummer}_{mot_namn}.pdf"
    pdf_path.write_bytes(r.content)

    # 6. Uppdatera fakturan i DB
    kor([
        "python3", str(DB_TOOLS / "db_invoices.py"),
        "--uppdatera", args.faktura_id,
        json.dumps({
            "pdf":    {"sokväg": str(pdf_path)},
            "status": "skapad",
        }, ensure_ascii=False)
    ])

    # 7. Uppdatera statistik på mottagaren
    kor([
        "python3", str(DB_TOOLS / "db_recipients.py"),
        "--uppdatera-statistik", f["mottagare_id"],
        str(f.get("totaler", {}).get("att_betala", 0))
    ])

    print(json.dumps({
        "status":        "ok",
        "faktura_id":    args.faktura_id,
        "nummer":        nummer,
        "doc_type":      doc_type,
        "pdf_sokväg":    str(pdf_path),
        "pdf_storlek":   len(r.content),
        "att_betala":    f.get("totaler", {}).get("att_betala", 0),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
