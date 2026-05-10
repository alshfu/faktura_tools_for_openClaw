#!/usr/bin/env python3
"""
db_invoices.py — CRUD för fakturaregistret (invoices.json v2).

Stöder:
- Skapa utkast (status=utkast)
- Status-övergångar: utkast → skapad → skickad → betald
- Soft-delete (status=borttagen, finns kvar för audit)
- Kreditering (skapar ny faktura med typ=kreditnota + länkar till original)
- Versionering vid varje ändring

Användning:
  --lista [--status STATUS] [--avsandare ORG]
  --hamta {faktura_id}
  --skapa-utkast '{json}'                  → returnerar faktura_id
  --uppdatera {faktura_id} '{partiell}'
  --andra-status {faktura_id} {ny_status}
  --markera-skickad {faktura_id} '{skickning_info}'
  --markera-betald {faktura_id} {datum}
  --ta-bort {faktura_id} --skal "..."
  --aterstall {faktura_id}
  --kreditera {faktura_id} --skal "..."     → skapar kreditnota, returnerar nytt id
"""
import argparse
import json
import sys
import uuid
from datetime import datetime, timezone, date, timedelta
from pathlib import Path

PROJEKT_ROT = Path(__file__).resolve().parent.parent.parent
DB_PATH     = PROJEKT_ROT / "data" / "invoices.json"

sys.path.insert(0, str(PROJEKT_ROT / "tools"))
from utils.ocr import generera_ocr


STATUSAR = ["utkast", "skapad", "skickad", "betald", "krediterad", "borttagen", "fel"]


def nu_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ladda() -> dict:
    if DB_PATH.exists():
        return json.loads(DB_PATH.read_text(encoding="utf-8"))
    return {"version": 2, "uppdaterad": nu_iso(), "fakturor": {}}


def spara(db: dict):
    db["uppdaterad"] = nu_iso()
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    DB_PATH.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")


def ok(data=None):
    out = {"status": "ok", "timestamp": nu_iso()}
    if data:
        out.update(data)
    print(json.dumps(out, ensure_ascii=False))


def fel(msg: str, kod: int = 1):
    print(json.dumps({"status": "fel", "meddelande": msg, "timestamp": nu_iso()},
                     ensure_ascii=False))
    sys.exit(kod)


def nytt_id() -> str:
    """Unikt ID i format fakt_YYYY_HHHHHH (året + 6 hex)."""
    year = datetime.now(timezone.utc).year
    return f"fakt_{year}_{uuid.uuid4().hex[:6]}"


def berakna_totaler(rader: list) -> dict:
    """Räkna ut netto, moms, brutto från rader."""
    netto = 0.0
    moms  = 0.0
    for r in rader:
        if r.get("typ") == "textrad" or r.get("textrad"):
            continue
        antal = float(r.get("antal", 0))
        apris = float(r.get("apris", 0))
        m_pct = float(r.get("moms_procent", 25)) / 100
        belopp = antal * apris
        netto += belopp
        moms  += belopp * m_pct
    brutto = netto + moms
    avrundning = round(brutto) - brutto
    att_betala = brutto + avrundning
    return {
        "netto":      round(netto, 2),
        "moms":       round(moms, 2),
        "brutto":     round(brutto, 2),
        "avrundning": round(avrundning, 2),
        "att_betala": round(att_betala, 2),
    }


def normalisera_rader(rader_input: list) -> list:
    """Säkerställ att varje rad har rätt struktur."""
    rader_ut = []
    for i, r in enumerate(rader_input, 1):
        if r.get("textrad") or r.get("typ") == "textrad":
            rader_ut.append({
                "nr":          i,
                "typ":         "textrad",
                "beskrivning": r.get("beskrivning", ""),
            })
        else:
            antal = float(r.get("antal", 0))
            apris = float(r.get("apris", 0))
            rader_ut.append({
                "nr":           i,
                "typ":          "tjanst",
                "beskrivning":  r.get("beskrivning", ""),
                "antal":        antal,
                "enhet":        r.get("enhet", "st"),
                "apris":        apris,
                "moms_procent": float(r.get("moms_procent", 25)),
                "belopp_netto": round(antal * apris, 2),
            })
    return rader_ut


def deep_merge(dest: dict, src: dict):
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dest.get(k), dict):
            deep_merge(dest[k], v)
        else:
            dest[k] = v


# ── Kommandon ─────────────────────────────────────────────────────────────────

def cmd_lista(args):
    db = ladda()
    rader = []
    for fid, v in db.get("fakturor", {}).items():
        if args.status and v.get("status") != args.status:
            continue
        if args.avsandare and v.get("avsandare_id") != args.avsandare:
            continue
        rader.append({
            "id":            fid,
            "nummer":        v.get("nummer"),
            "status":        v.get("status"),
            "avsandare_id":  v.get("avsandare_id"),
            "mottagare_id":  v.get("mottagare_id"),
            "datum":         v.get("datum", {}).get("faktura"),
            "att_betala":    v.get("totaler", {}).get("att_betala", 0),
            "skapad":        v.get("skapad_datum"),
        })
    rader.sort(key=lambda x: x.get("nummer") or 0, reverse=True)
    ok({"antal": len(rader), "fakturor": rader})


def cmd_hamta(args):
    db = ladda()
    fid = args.faktura_id
    if fid not in db.get("fakturor", {}):
        fel(f"Faktura {fid} hittades inte")
    ok({"faktura": db["fakturor"][fid]})


def cmd_skapa_utkast(args):
    try:
        payload = json.loads(args.json_data)
    except json.JSONDecodeError as e:
        fel(f"Ogiltig JSON: {e}")

    avs_id = payload.get("avsandare_id")
    mot_id = payload.get("mottagare_id")
    nummer = payload.get("nummer")
    rader  = payload.get("rader", [])

    if not avs_id:
        fel("avsandare_id krävs")
    if not mot_id:
        fel("mottagare_id krävs")
    if not nummer:
        fel("nummer krävs")
    if not rader:
        fel("rader får ej vara tom")

    db = ladda()
    db.setdefault("fakturor", {})

    fid = payload.get("id") or nytt_id()
    rader_norm = normalisera_rader(rader)
    totaler    = berakna_totaler(rader_norm)

    betaldagar      = payload.get("betalningsvillkor_dagar", 30)
    fakturadatum    = payload.get("faktura_datum") or date.today().isoformat()
    forfallodatum   = payload.get("forfallo_datum") or \
                      (date.fromisoformat(fakturadatum) + timedelta(days=betaldagar)).isoformat()

    db["fakturor"][fid] = {
        "id":          fid,
        "version":     1,
        "skapad_datum":    nu_iso(),
        "uppdaterad_datum": nu_iso(),
        "nummer":      nummer,
        "status":      "utkast",
        "avsandare_id": avs_id,
        "mottagare_id": mot_id,

        "datum": {
            "faktura":  fakturadatum,
            "forfallo": forfallodatum,
            "betalningsvillkor_dagar": betaldagar,
        },

        "rader":   rader_norm,
        "totaler": totaler,

        "meta": {
            "referens": payload.get("referens", ""),
            "momslage": payload.get("momslage", ""),
            "ocr":      payload.get("ocr") or generera_ocr(nummer),
            "valuta":   payload.get("valuta", "SEK"),
        },

        "skickning": {
            "miljo":            payload.get("miljo", "sandbox"),
            "metod":            None,
            "skickad_datum":    None,
            "fakturan_nu_id":   None,
            "mottagare_epost":  payload.get("mottagare_epost", ""),
        },

        "pdf": {
            "sokväg":         None,
            "design_shablon": payload.get("design_shablon", "klassisk_svart"),
        },

        "relationer": {
            "krediterad_av": None,
            "kredit_for":    payload.get("kredit_for"),
            "ersatter":      payload.get("ersatter"),
        },

        "anteckningar": [],
    }

    spara(db)
    ok({
        "meddelande":  "Utkast skapat",
        "faktura_id":  fid,
        "nummer":      nummer,
        "att_betala":  totaler["att_betala"],
    })


def cmd_uppdatera(args):
    try:
        partiell = json.loads(args.json_data)
    except json.JSONDecodeError as e:
        fel(f"Ogiltig JSON: {e}")

    db = ladda()
    fid = args.faktura_id
    if fid not in db.get("fakturor", {}):
        fel(f"Faktura {fid} hittades inte")

    # Om rader uppdateras → räkna om totaler
    if "rader" in partiell:
        partiell["rader"]   = normalisera_rader(partiell["rader"])
        partiell["totaler"] = berakna_totaler(partiell["rader"])

    deep_merge(db["fakturor"][fid], partiell)
    db["fakturor"][fid]["uppdaterad_datum"] = nu_iso()
    db["fakturor"][fid]["version"] = db["fakturor"][fid].get("version", 1) + 1
    spara(db)
    ok({"meddelande": "Faktura uppdaterad", "faktura_id": fid,
        "ny_version": db["fakturor"][fid]["version"]})


def cmd_andra_status(args):
    db = ladda()
    fid = args.faktura_id
    if fid not in db.get("fakturor", {}):
        fel(f"Faktura {fid} hittades inte")
    if args.ny_status not in STATUSAR:
        fel(f"Ogiltig status. Tillåtna: {', '.join(STATUSAR)}")
    db["fakturor"][fid]["status"] = args.ny_status
    db["fakturor"][fid]["uppdaterad_datum"] = nu_iso()
    spara(db)
    ok({"meddelande": "Status ändrad", "faktura_id": fid, "ny_status": args.ny_status})


def cmd_markera_skickad(args):
    try:
        skickning = json.loads(args.json_data)
    except json.JSONDecodeError as e:
        fel(f"Ogiltig JSON: {e}")

    db = ladda()
    fid = args.faktura_id
    if fid not in db.get("fakturor", {}):
        fel(f"Faktura {fid} hittades inte")
    skickning.setdefault("skickad_datum", nu_iso())
    deep_merge(db["fakturor"][fid].setdefault("skickning", {}), skickning)
    db["fakturor"][fid]["status"] = "skickad"
    db["fakturor"][fid]["uppdaterad_datum"] = nu_iso()
    spara(db)
    ok({"meddelande": "Faktura markerad som skickad", "faktura_id": fid})


def cmd_markera_betald(args):
    db = ladda()
    fid = args.faktura_id
    if fid not in db.get("fakturor", {}):
        fel(f"Faktura {fid} hittades inte")
    db["fakturor"][fid].setdefault("betalning", {})["betald_datum"] = args.datum
    db["fakturor"][fid]["status"] = "betald"
    db["fakturor"][fid]["uppdaterad_datum"] = nu_iso()
    spara(db)
    ok({"meddelande": "Faktura markerad som betald", "faktura_id": fid,
        "betald_datum": args.datum})


def cmd_ta_bort(args):
    """Soft delete — status=borttagen. Bevarar för audit."""
    db = ladda()
    fid = args.faktura_id
    if fid not in db.get("fakturor", {}):
        fel(f"Faktura {fid} hittades inte")
    db["fakturor"][fid]["status"] = "borttagen"
    db["fakturor"][fid]["uppdaterad_datum"] = nu_iso()
    db["fakturor"][fid].setdefault("anteckningar", []).append({
        "datum":    nu_iso(),
        "typ":      "borttagning",
        "skal":     args.skal or "Ingen anledning angiven",
    })
    spara(db)
    ok({"meddelande": "Faktura borttagen (soft delete)", "faktura_id": fid})


def cmd_aterstall(args):
    db = ladda()
    fid = args.faktura_id
    if fid not in db.get("fakturor", {}):
        fel(f"Faktura {fid} hittades inte")
    if db["fakturor"][fid]["status"] != "borttagen":
        fel("Endast borttagna fakturor kan återställas")
    db["fakturor"][fid]["status"] = "skapad"
    db["fakturor"][fid]["uppdaterad_datum"] = nu_iso()
    db["fakturor"][fid].setdefault("anteckningar", []).append({
        "datum": nu_iso(),
        "typ":   "aterstallning",
    })
    spara(db)
    ok({"meddelande": "Faktura återställd", "faktura_id": fid})


def cmd_kreditera(args):
    """
    Skapar en kreditnota för fakturan.
    - Ny faktura med doc_type=kreditnota, negativa belopp
    - Original-fakturans status ändras till krediterad
    - Båda länkas via relationer
    """
    db = ladda()
    original_id = args.faktura_id
    if original_id not in db.get("fakturor", {}):
        fel(f"Faktura {original_id} hittades inte")

    original = db["fakturor"][original_id]
    if original["status"] in ("krediterad", "borttagen"):
        fel(f"Faktura kan inte krediteras (status: {original['status']})")

    # Hämta nästa nummer från avsändarens räknare
    sys.path.insert(0, str(PROJEKT_ROT / "tools" / "db"))
    senders_db_path = PROJEKT_ROT / "data" / "senders.json"
    if senders_db_path.exists():
        senders_db = json.loads(senders_db_path.read_text(encoding="utf-8"))
        avs = senders_db.get("avsandare", {}).get(original["avsandare_id"], {})
        nytt_nummer = avs.get("fakturering", {}).get("nasta_faktura_nummer", original["nummer"] + 1)
        # Inkrementera
        senders_db["avsandare"][original["avsandare_id"]].setdefault("fakturering", {})["nasta_faktura_nummer"] = nytt_nummer + 1
        senders_db["uppdaterad"] = nu_iso()
        senders_db_path.write_text(json.dumps(senders_db, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        nytt_nummer = original["nummer"] + 1000

    # Negativa rader
    nya_rader = []
    for r in original["rader"]:
        if r["typ"] == "textrad":
            nya_rader.append(dict(r))
        else:
            ny = dict(r)
            ny["antal"]        = -abs(r["antal"])
            ny["belopp_netto"] = -abs(r["belopp_netto"])
            nya_rader.append(ny)

    kredit_id = nytt_id()
    totaler   = berakna_totaler(nya_rader)

    db["fakturor"][kredit_id] = {
        "id":          kredit_id,
        "version":     1,
        "skapad_datum":    nu_iso(),
        "uppdaterad_datum": nu_iso(),
        "nummer":      nytt_nummer,
        "doc_type":    "kreditnota",
        "status":      "utkast",
        "avsandare_id": original["avsandare_id"],
        "mottagare_id": original["mottagare_id"],

        "datum": {
            "faktura":  date.today().isoformat(),
            "forfallo": date.today().isoformat(),
            "betalningsvillkor_dagar": 0,
        },

        "rader":   nya_rader,
        "totaler": totaler,

        "meta": {
            "referens": f"Kreditnota för faktura nr {original['nummer']}",
            "momslage": original["meta"].get("momslage", ""),
            "ocr":      generera_ocr(nytt_nummer),
            "valuta":   original["meta"].get("valuta", "SEK"),
        },

        "skickning": {
            "miljo":          original["skickning"].get("miljo", "sandbox"),
            "metod":          None,
            "skickad_datum":  None,
            "mottagare_epost": original["skickning"].get("mottagare_epost", ""),
        },

        "pdf": {
            "sokväg":         None,
            "design_shablon": original["pdf"].get("design_shablon", "klassisk_svart"),
        },

        "relationer": {
            "krediterad_av": None,
            "kredit_for":    original_id,
            "ersatter":      None,
        },

        "anteckningar": [{
            "datum": nu_iso(),
            "typ":   "kreditering",
            "skal":  args.skal or "Ingen anledning angiven",
        }],
    }

    # Uppdatera originalet
    original["status"] = "krediterad"
    original["uppdaterad_datum"] = nu_iso()
    original.setdefault("relationer", {})["krediterad_av"] = kredit_id
    original.setdefault("anteckningar", []).append({
        "datum":      nu_iso(),
        "typ":        "krediterad",
        "kredit_id":  kredit_id,
        "skal":       args.skal or "Ingen anledning angiven",
    })

    spara(db)
    ok({
        "meddelande":       "Kreditnota skapad",
        "kredit_faktura_id": kredit_id,
        "kredit_nummer":     nytt_nummer,
        "original_id":       original_id,
        "att_kreditera":     totaler["att_betala"],
    })


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--lista",          action="store_true")
    p.add_argument("--status",         help="Filtrera --lista på status")
    p.add_argument("--avsandare",      help="Filtrera --lista på avsändare")
    p.add_argument("--hamta",          metavar="ID")
    p.add_argument("--skapa-utkast",   metavar="JSON", dest="skapa")
    p.add_argument("--uppdatera",      metavar="ID")
    p.add_argument("--andra-status",   nargs=2, metavar=("ID","STATUS"), dest="andra")
    p.add_argument("--markera-skickad", metavar="ID", dest="markera_skickad")
    p.add_argument("--markera-betald",  nargs=2, metavar=("ID","DATUM"), dest="markera_betald")
    p.add_argument("--ta-bort",        metavar="ID", dest="ta_bort")
    p.add_argument("--aterstall",      metavar="ID")
    p.add_argument("--kreditera",      metavar="ID")
    p.add_argument("--skal",           help="Anledning till borttagning/kreditering")
    p.add_argument("json_data",        nargs="?")
    args = p.parse_args()

    if args.lista:
        cmd_lista(args)
    elif args.hamta:
        args.faktura_id = args.hamta; cmd_hamta(args)
    elif args.skapa:
        args.json_data = args.skapa; cmd_skapa_utkast(args)
    elif args.uppdatera:
        args.faktura_id = args.uppdatera
        if not args.json_data: fel("--uppdatera kräver JSON-data")
        cmd_uppdatera(args)
    elif args.andra:
        args.faktura_id = args.andra[0]
        args.ny_status  = args.andra[1]
        cmd_andra_status(args)
    elif args.markera_skickad:
        args.faktura_id = args.markera_skickad
        if not args.json_data: fel("--markera-skickad kräver JSON-data")
        cmd_markera_skickad(args)
    elif args.markera_betald:
        args.faktura_id = args.markera_betald[0]
        args.datum      = args.markera_betald[1]
        cmd_markera_betald(args)
    elif args.ta_bort:
        args.faktura_id = args.ta_bort; cmd_ta_bort(args)
    elif args.aterstall:
        args.faktura_id = args.aterstall; cmd_aterstall(args)
    elif args.kreditera:
        args.faktura_id = args.kreditera; cmd_kreditera(args)
    else:
        p.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
