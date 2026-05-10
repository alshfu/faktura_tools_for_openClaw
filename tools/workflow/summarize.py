#!/usr/bin/env python3
"""
summarize.py — Genererar fakturasammanfattning för bekräftelse i WhatsApp.

Hämtar all data från databaserna och formaterar enligt invoice/summary.txt.

Användning:
  python3 summarize.py --faktura-id {id}
  python3 summarize.py --faktura-id {id} --skicka-till +46735272989
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

PROJEKT_ROT = Path(__file__).resolve().parent.parent.parent
DB_TOOLS    = PROJEKT_ROT / "tools" / "db"
MSG_TOOLS   = PROJEKT_ROT / "tools" / "messaging"


def kor(cmd: list) -> dict:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    try:
        return json.loads(r.stdout)
    except Exception:
        return {"status": "fel", "meddelande": r.stderr or r.stdout}


def fmt_sek(v: float) -> str:
    return f"{v:,.2f}".replace(",", " ").replace(".", ",") + " SEK"


def formatera_rader(rader: list) -> str:
    out = []
    for r in rader:
        if r.get("typ") == "textrad":
            out.append(f"   {r['nr']}. 📝 {r.get('beskrivning','')}")
        else:
            antal = r.get("antal", 0)
            apris = r.get("apris", 0)
            enhet = r.get("enhet", "st")
            mpct  = r.get("moms_procent", 25)
            belopp = r.get("belopp_netto", 0)
            out.append(
                f"   {r['nr']}. {r.get('beskrivning','')}\n"
                f"      {antal} {enhet} × {apris:,.2f} kr (moms {mpct:.0f}%) = {fmt_sek(belopp)}"
            )
    return "\n".join(out)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--faktura-id",   required=True, dest="faktura_id")
    p.add_argument("--skicka-till",  dest="skicka_till",
                   help="Om angiven — skicka direkt till WhatsApp")
    args = p.parse_args()

    # 1. Hämta fakturan
    fakt = kor(["python3", str(DB_TOOLS / "db_invoices.py"), "--hamta", args.faktura_id])
    if fakt.get("status") != "ok":
        print(json.dumps(fakt, ensure_ascii=False)); sys.exit(1)
    f = fakt["faktura"]

    # 2. Hämta avsändare
    avs = kor(["python3", str(DB_TOOLS / "db_senders.py"), "--hamta", f["avsandare_id"]])
    if avs.get("status") != "ok":
        print(json.dumps(avs, ensure_ascii=False)); sys.exit(1)
    a = avs["avsandare"]

    # 3. Hämta mottagare
    mot = kor(["python3", str(DB_TOOLS / "db_recipients.py"), "--hamta", f["mottagare_id"]])
    if mot.get("status") != "ok":
        print(json.dumps(mot, ensure_ascii=False)); sys.exit(1)
    m = mot["mottagare"]

    # 4. Hämta design-namn
    design_id = f.get("pdf", {}).get("design_shablon", "klassisk_svart")
    design = kor(["python3", str(DB_TOOLS / "db_templates.py"), "--hamta", design_id])
    design_namn = design.get("shablon", {}).get("namn", design_id) if design.get("status") == "ok" else design_id

    # 5. Bygg variabler för shablonen
    madr = m.get("adress", {})
    madr_str = " ".join(filter(None, [madr.get("gata", ""),
                                       f"{madr.get('postnummer','')} {madr.get('stad','')}"]))
    miljo = f.get("skickning", {}).get("miljo", "sandbox")

    variabler = {
        "nummer":              f.get("nummer"),
        "design_namn":         design_namn,
        "avsandare_namn":      a.get("foretag", {}).get("namn", "—"),
        "avsandare_org":       a.get("foretag", {}).get("org_nummer", "—"),
        "avsandare_bankgiro":  a.get("bank", {}).get("bankgiro", "—"),
        "mottagare_namn":      m.get("foretag", {}).get("namn", "—"),
        "mottagare_org":       m.get("foretag", {}).get("org_nummer", "—"),
        "mottagare_epost":     m.get("kontakt", {}).get("epost", "—"),
        "mottagare_adress":    madr_str,
        "faktura_datum":       f.get("datum", {}).get("faktura", "—"),
        "forfallo_datum":      f.get("datum", {}).get("forfallo", "—"),
        "betaldagar":          f.get("datum", {}).get("betalningsvillkor_dagar", 30),
        "referens":            f.get("meta", {}).get("referens", "—"),
        "momslage":            f.get("meta", {}).get("momslage", "—"),
        "miljo_emoji":         "🧪" if miljo == "sandbox" else "🚀",
        "miljo":               miljo,
        "rader_lista":         formatera_rader(f.get("rader", [])),
        "netto":               fmt_sek(f.get("totaler", {}).get("netto", 0)),
        "moms":                fmt_sek(f.get("totaler", {}).get("moms", 0)),
        "brutto":              fmt_sek(f.get("totaler", {}).get("att_betala", 0)),
    }

    # 6. Skicka eller skriv ut
    if args.skicka_till:
        r = subprocess.run([
            "python3", str(MSG_TOOLS / "send_template.py"),
            "--shablon",   "invoice/summary.txt",
            "--till",      args.skicka_till,
            "--variabler", json.dumps(variabler, ensure_ascii=False)
        ], capture_output=True, text=True)
        print(r.stdout)
    else:
        # Bara skriv ut variablerna (för debug)
        print(json.dumps({"status": "ok", "variabler": variabler}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
