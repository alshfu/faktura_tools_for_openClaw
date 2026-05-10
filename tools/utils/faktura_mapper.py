#!/usr/bin/env python3
"""
faktura_mapper.py — Mappar internt svenskt fakturaschema till Faktura Constructor.

Internt format (vårt JSON med svenska nycklar):
{
  "avsandare": {...},
  "mottagare": {...},
  "faktura_info": {...},
  "rader": [...],
  "nummer": 893,
  "design_shablon": "klassisk_svart"
}

Output: Faktura Constructor JSON som skickas till http://localhost:3030/pdf
"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

# Lägg till projektrot i sys.path för relativa imports
PROJEKT_ROT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJEKT_ROT / "tools"))

from utils.ocr import generera_ocr
from utils.vat import generera_vat


PRESETS_PATH = PROJEKT_ROT / "templates" / "design" / "presets.json"


def ladda_design_style(shablon_id: str, anpassningar: dict = None) -> dict:
    """Hämtar style från presets.json + applicerar eventuella anpassningar."""
    if not PRESETS_PATH.exists():
        return {}
    presets = json.loads(PRESETS_PATH.read_text(encoding="utf-8"))
    shabloner = presets.get("shabloner", {})
    if shablon_id not in shabloner:
        shablon_id = "klassisk_svart"
    style = dict(shabloner.get(shablon_id, {}).get("style", {}))
    if anpassningar:
        style.update(anpassningar)
    return style


def mappa(internt_doc: dict) -> dict:
    """Konverterar internt format → Faktura Constructor."""
    avs   = internt_doc.get("avsandare", {})
    mot   = internt_doc.get("mottagare", {})
    fmeta = internt_doc.get("faktura_info", {})
    rader = internt_doc.get("rader", [])

    # ── Datum ──
    betaldagar     = fmeta.get("betalningsvillkor_dagar", 30)
    fakturadatum   = fmeta.get("faktura_datum") or date.today().isoformat()
    forfallodatum  = fmeta.get("forfallo_datum")
    if not forfallodatum:
        dt = date.fromisoformat(fakturadatum)
        forfallodatum = (dt + timedelta(days=betaldagar)).isoformat()

    nummer = internt_doc.get("nummer", 1)

    # ── Sender ──
    aadr = avs.get("adress", {})
    foretag = avs.get("foretag", avs)  # stöd både flat och nested struktur
    bank    = avs.get("bank", avs)
    kontakt = avs.get("kontakt", avs)
    fakt    = avs.get("fakturering", {})

    org_nummer = foretag.get("org_nummer", avs.get("org_nummer", ""))
    moms_nr    = foretag.get("moms_nummer") or (generera_vat(org_nummer) if org_nummer else "")

    address_rader = []
    if aadr.get("gata"):
        address_rader.append(aadr.get("gata"))
    pn_stad = " ".join(filter(None, [aadr.get("postnummer", ""), aadr.get("stad", "")])).strip()
    if pn_stad:
        address_rader.append(pn_stad)

    contact_rader = []
    if kontakt.get("epost"):   contact_rader.append(kontakt["epost"])
    if kontakt.get("telefon"): contact_rader.append(kontakt["telefon"])
    if kontakt.get("webb"):    contact_rader.append(kontakt["webb"])

    sender = {
        "name":     foretag.get("namn", avs.get("namn", "")),
        "tagline":  foretag.get("tagline", ""),
        "orgnr":    org_nummer,
        "momsnr":   moms_nr,
        "address":  address_rader,
        "contact":  contact_rader,
        "bankgiro": bank.get("bankgiro", avs.get("bankgiro", "")),
        "iban":     bank.get("iban", avs.get("iban", "")),
        "bic":      bank.get("bic", avs.get("bic", "")),
        "bank":     bank.get("bank_namn", ""),
    }

    # ── Client ──
    madr = mot.get("adress", {})
    m_foretag = mot.get("foretag", mot)
    m_kontakt = mot.get("kontakt", mot)

    client_address = []
    if madr.get("gata"):
        client_address.append(madr.get("gata"))
    m_pn_stad = " ".join(filter(None, [madr.get("postnummer",""), madr.get("stad","")])).strip()
    if m_pn_stad:
        client_address.append(m_pn_stad)

    client = {
        "name":    m_foretag.get("namn", mot.get("namn", "")),
        "orgnr":   m_foretag.get("org_nummer", mot.get("org_nummer", "")),
        "email":   m_kontakt.get("epost", mot.get("epost", "")),
        "phone":   m_kontakt.get("telefon", mot.get("telefon", "")),
        "attn":    m_foretag.get("kontaktperson", ""),
        "address": client_address,
    }

    # ── Items ──
    items = []
    moms_default = fakt.get("moms_procent_default", 25) / 100

    for i, rad in enumerate(rader, start=1):
        if rad.get("textrad") or rad.get("typ") == "textrad":
            # Faktura Constructor saknar text-rader → lägg som item med qty=0, price=0
            items.append({
                "id":    i,
                "title": rad.get("beskrivning", ""),
                "qty":   0,
                "price": 0,
            })
        else:
            item = {
                "id":    i,
                "title": rad.get("beskrivning", ""),
                "qty":   float(rad.get("antal", 0)),
                "price": float(rad.get("apris", 0)),
                "unit":  rad.get("enhet", "st"),
            }
            if "moms_procent" in rad:
                item["momsRate"] = float(rad["moms_procent"]) / 100
            items.append(item)

    # ── Meta ──
    meta = {
        "nr":             str(nummer),
        "issuedShort":    fakturadatum,
        "dueShort":       forfallodatum,
        "terms":          f"{betaldagar} dagar netto",
        "ocr":            fmeta.get("ocr") or generera_ocr(nummer),
        "currency":       "SEK",
        "currencySymbol": "kr",
    }
    if fmeta.get("referens"):
        meta["ref"] = fmeta["referens"]

    # ── Legal ──
    legal = {}
    if fmeta.get("momslage"):
        legal["notes"] = fmeta["momslage"]
    if foretag.get("f_skatt", True):
        legal["fskatt"] = "Innehar F-skattsedel."
    if avs.get("fakturering", {}).get("faktura_villkor_text"):
        legal["payment"] = avs["fakturering"]["faktura_villkor_text"]

    # ── Style ──
    design = avs.get("design", {})
    shablon_id   = internt_doc.get("design_shablon") or design.get("shablon_id", "klassisk_svart")
    anpassningar = design.get("anpassningar", {})
    style = ladda_design_style(shablon_id, anpassningar)

    # ── Doc type ──
    docType = internt_doc.get("doc_type", "faktura")

    return {
        "docType":  docType,
        "locale":   "sv-SE",
        "sender":   sender,
        "client":   client,
        "meta":     meta,
        "items":    items,
        "momsRate": moms_default,
        "legal":    legal,
        "style":    style,
    }


# ── CLI för testning ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--fil", required=True, help="Internt JSON-format")
    args = p.parse_args()

    internt = json.loads(Path(args.fil).read_text(encoding="utf-8"))
    fc_doc  = mappa(internt)
    print(json.dumps(fc_doc, ensure_ascii=False, indent=2))
