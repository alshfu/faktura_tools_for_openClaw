#!/usr/bin/env python3
"""
db_senders.py — CRUD för avsändarregistret (senders.json v2).

Nytt schema med versionering, telefonkopplingar, designinställningar
och statistik. Returnerar alltid JSON.

Användning:
  --lista
  --hamta {org_nummer}
  --finns {org_nummer}
  --sok "{namn_eller_org}"
  --lagg-till '{json}'
  --uppdatera {org_nummer} '{partiell_json}'
  --ta-bort {org_nummer}              (soft delete: aktiv=false)
  --aterstall {org_nummer}            (aktiv=true)
  --koppla-telefon {org_nummer} {telefon}
  --avkoppla-telefon {org_nummer} {telefon}
  --nasta-fakturanummer {org_nummer}
  --uppdatera-nasta-fakturanummer {org_nummer} {N}
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Bestäm projektrot
PROJEKT_ROT = Path(__file__).resolve().parent.parent.parent
DB_PATH     = PROJEKT_ROT / "data" / "senders.json"


def nu_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ladda() -> dict:
    if DB_PATH.exists():
        return json.loads(DB_PATH.read_text(encoding="utf-8"))
    return {"version": 2, "uppdaterad": nu_iso(), "avsandare": {}}


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


# ── Schema-validering ─────────────────────────────────────────────────────────

OBLIGATORISKA = ["org_nummer"]


def validera_org_nummer(org: str) -> bool:
    """Svenskt org_nummer: 10 siffror med eller utan bindestreck."""
    rensat = org.replace("-", "").replace(" ", "")
    return rensat.isdigit() and len(rensat) == 10


def generera_vat(org: str) -> str:
    rensat = org.replace("-", "").replace(" ", "")
    return f"SE{rensat}01"


def nytt_record(payload: dict) -> dict:
    """Bygger fullständigt schema-v2 record från användarinmatning."""
    org = payload.get("org_nummer", "")
    foretag = payload.get("foretag", {})
    adress  = payload.get("adress", {})
    kontakt = payload.get("kontakt", {})
    bank    = payload.get("bank", {})
    fakt_nu = payload.get("fakturan_nu", {})
    design  = payload.get("design", {})
    fakt    = payload.get("fakturering", {})

    return {
        "id": org,
        "version": 1,
        "skapad_datum": nu_iso(),
        "uppdaterad_datum": nu_iso(),
        "aktiv": True,

        "foretag": {
            "namn":        foretag.get("namn", payload.get("namn", "")),
            "org_nummer":  org,
            "moms_nummer": foretag.get("moms_nummer", generera_vat(org)),
            "f_skatt":     foretag.get("f_skatt", True),
            "tagline":     foretag.get("tagline", ""),
        },

        "adress": {
            "gata":       adress.get("gata", ""),
            "postnummer": adress.get("postnummer", ""),
            "stad":       adress.get("stad", ""),
            "land":       adress.get("land", "SE"),
        },

        "kontakt": {
            "epost":   kontakt.get("epost", ""),
            "telefon": kontakt.get("telefon", ""),
            "webb":    kontakt.get("webb", ""),
        },

        "bank": {
            "bankgiro":  bank.get("bankgiro", ""),
            "plusgiro":  bank.get("plusgiro", ""),
            "iban":      bank.get("iban", ""),
            "bic":       bank.get("bic", ""),
            "bank_namn": bank.get("bank_namn", ""),
            "valuta":    bank.get("valuta", "SEK"),
        },

        "fakturan_nu": {
            "aktiverad":     fakt_nu.get("aktiverad", False),
            "api_nyckel":    fakt_nu.get("api_nyckel", ""),
            "api_losenord":  fakt_nu.get("api_losenord", ""),
            "miljo_default": fakt_nu.get("miljo_default", "sandbox"),
            "shablon_instaellningar": fakt_nu.get("shablon_instaellningar", {
                "invoice_template": "croatia",
                "show_product_code": False,
                "locale": "sv",
                "currency": "SEK",
            }),
        },

        "design": {
            "shablon_id":    design.get("shablon_id", "klassisk_svart"),
            "anpassningar":  design.get("anpassningar", {}),
        },

        "fakturering": {
            "betalningsvillkor_dagar_default": fakt.get("betalningsvillkor_dagar_default", 30),
            "moms_procent_default":            fakt.get("moms_procent_default", 25),
            "nasta_faktura_nummer":            fakt.get("nasta_faktura_nummer", 1),
            "faktura_villkor_text":            fakt.get("faktura_villkor_text", ""),
        },

        "telefon_kopplingar": payload.get("telefon_kopplingar", []),
    }


def render_lista(db: dict) -> list:
    return [
        {
            "org_nummer":      v["foretag"]["org_nummer"],
            "namn":            v["foretag"]["namn"],
            "aktiv":           v.get("aktiv", True),
            "har_api":         v.get("fakturan_nu", {}).get("aktiverad", False),
            "nasta_fakturanr": v.get("fakturering", {}).get("nasta_faktura_nummer", 1),
            "telefoner":       v.get("telefon_kopplingar", []),
        }
        for v in db.get("avsandare", {}).values()
    ]


# ── Kommandon ─────────────────────────────────────────────────────────────────

def cmd_lista(args):
    db = ladda()
    rader = render_lista(db)
    ok({"antal": len(rader), "avsandare": rader})


def cmd_hamta(args):
    db = ladda()
    org = args.org_nummer
    if org not in db.get("avsandare", {}):
        fel(f"Avsändare {org} hittades inte")
    import copy
    record = copy.deepcopy(db["avsandare"][org])
    intern = getattr(args, "intern", False)
    # Maskera känslig data om det inte är ett internt anrop
    if not intern and record.get("fakturan_nu", {}).get("api_losenord"):
        record["fakturan_nu"]["api_losenord"] = "***maskerad***"
    ok({"avsandare": record})


def cmd_finns(args):
    db = ladda()
    org = args.org_nummer
    finns = org in db.get("avsandare", {})
    result = {"org_nummer": org, "finns": finns}
    if finns:
        v = db["avsandare"][org]
        result["namn"]       = v["foretag"]["namn"]
        result["aktiv"]      = v.get("aktiv", True)
        result["har_api"]    = v.get("fakturan_nu", {}).get("aktiverad", False)
    ok(result)


def cmd_sok(args):
    db = ladda()
    query = args.sokterm.lower().strip()
    if not query:
        ok({"antal": 0, "treff": []})
        return
    treff = [
        {
            "org_nummer": v["foretag"]["org_nummer"],
            "namn":       v["foretag"]["namn"],
            "aktiv":      v.get("aktiv", True),
        }
        for v in db.get("avsandare", {}).values()
        if query in v["foretag"]["namn"].lower()
        or query in v["foretag"]["org_nummer"].lower()
    ]
    ok({"antal": len(treff), "treff": treff})


def cmd_lagg_till(args):
    try:
        payload = json.loads(args.json_data)
    except json.JSONDecodeError as e:
        fel(f"Ogiltig JSON: {e}")

    org = payload.get("org_nummer")
    if not org:
        fel("Obligatoriskt fält saknas: org_nummer")
    if not validera_org_nummer(org):
        fel(f"Ogiltigt org_nummer: {org} (måste vara 10 siffror)")

    db = ladda()
    db.setdefault("avsandare", {})

    if org in db["avsandare"]:
        fel(f"Avsändare {org} finns redan. Använd --uppdatera.")

    db["avsandare"][org] = nytt_record(payload)
    spara(db)
    ok({"meddelande": "Avsändare tillagd", "org_nummer": org,
        "namn": db["avsandare"][org]["foretag"]["namn"]})


def deep_merge(dest: dict, src: dict):
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dest.get(k), dict):
            deep_merge(dest[k], v)
        else:
            dest[k] = v


def cmd_uppdatera(args):
    try:
        partiell = json.loads(args.json_data)
    except json.JSONDecodeError as e:
        fel(f"Ogiltig JSON: {e}")

    db = ladda()
    org = args.org_nummer
    if org not in db.get("avsandare", {}):
        fel(f"Avsändare {org} hittades inte")

    deep_merge(db["avsandare"][org], partiell)
    db["avsandare"][org]["uppdaterad_datum"] = nu_iso()
    db["avsandare"][org]["version"] = db["avsandare"][org].get("version", 1) + 1
    spara(db)
    ok({"meddelande": "Avsändare uppdaterad", "org_nummer": org,
        "ny_version": db["avsandare"][org]["version"]})


def cmd_ta_bort(args):
    """Soft delete — aktiv=false."""
    db = ladda()
    org = args.org_nummer
    if org not in db.get("avsandare", {}):
        fel(f"Avsändare {org} hittades inte")
    db["avsandare"][org]["aktiv"] = False
    db["avsandare"][org]["uppdaterad_datum"] = nu_iso()
    spara(db)
    ok({"meddelande": "Avsändare deaktiverad (soft delete)", "org_nummer": org})


def cmd_aterstall(args):
    db = ladda()
    org = args.org_nummer
    if org not in db.get("avsandare", {}):
        fel(f"Avsändare {org} hittades inte")
    db["avsandare"][org]["aktiv"] = True
    db["avsandare"][org]["uppdaterad_datum"] = nu_iso()
    spara(db)
    ok({"meddelande": "Avsändare återställd", "org_nummer": org})


def cmd_koppla_telefon(args):
    db = ladda()
    org = args.org_nummer
    tel = args.telefon
    if org not in db.get("avsandare", {}):
        fel(f"Avsändare {org} hittades inte")
    kopplingar = db["avsandare"][org].setdefault("telefon_kopplingar", [])
    if tel not in kopplingar:
        kopplingar.append(tel)
    db["avsandare"][org]["uppdaterad_datum"] = nu_iso()
    spara(db)
    ok({"meddelande": "Telefon kopplad", "org_nummer": org, "telefon": tel,
        "alla_kopplingar": kopplingar})


def cmd_avkoppla_telefon(args):
    db = ladda()
    org = args.org_nummer
    tel = args.telefon
    if org not in db.get("avsandare", {}):
        fel(f"Avsändare {org} hittades inte")
    kopplingar = db["avsandare"][org].get("telefon_kopplingar", [])
    if tel in kopplingar:
        kopplingar.remove(tel)
    db["avsandare"][org]["telefon_kopplingar"] = kopplingar
    db["avsandare"][org]["uppdaterad_datum"] = nu_iso()
    spara(db)
    ok({"meddelande": "Telefon avkopplad", "alla_kopplingar": kopplingar})


def cmd_nasta_fakturanummer(args):
    db = ladda()
    org = args.org_nummer
    if org not in db.get("avsandare", {}):
        fel(f"Avsändare {org} hittades inte")
    nr = db["avsandare"][org].get("fakturering", {}).get("nasta_faktura_nummer", 1)
    ok({"org_nummer": org, "nasta_faktura_nummer": nr})


def cmd_uppdatera_nasta_fakturanummer(args):
    db = ladda()
    org = args.org_nummer
    if org not in db.get("avsandare", {}):
        fel(f"Avsändare {org} hittades inte")
    db["avsandare"][org].setdefault("fakturering", {})["nasta_faktura_nummer"] = args.nummer
    db["avsandare"][org]["uppdaterad_datum"] = nu_iso()
    spara(db)
    ok({"meddelande": "Nästa fakturanummer uppdaterat",
        "org_nummer": org, "nasta_faktura_nummer": args.nummer})


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description="CRUD för avsändarregistret")
    p.add_argument("--lista",      action="store_true")
    p.add_argument("--hamta",        metavar="ORG")
    p.add_argument("--hamta-intern", metavar="ORG", dest="hamta_intern")
    p.add_argument("--finns",      metavar="ORG")
    p.add_argument("--sok",        metavar="TERM")
    p.add_argument("--lagg-till",  metavar="JSON", dest="lagg_till")
    p.add_argument("--uppdatera",  metavar="ORG")
    p.add_argument("--ta-bort",    metavar="ORG", dest="ta_bort")
    p.add_argument("--aterstall",  metavar="ORG")
    p.add_argument("--koppla-telefon",    nargs=2, metavar=("ORG","TEL"), dest="koppla")
    p.add_argument("--avkoppla-telefon",  nargs=2, metavar=("ORG","TEL"), dest="avkoppla")
    p.add_argument("--nasta-fakturanummer", metavar="ORG", dest="nasta_nr")
    p.add_argument("--uppdatera-nasta-fakturanummer", nargs=2, metavar=("ORG","N"),
                   dest="upd_nasta")
    p.add_argument("json_data", nargs="?")

    args = p.parse_args()

    if args.lista:
        cmd_lista(args)
    elif args.hamta:
        args.org_nummer = args.hamta; args.intern = False; cmd_hamta(args)
    elif args.hamta_intern:
        args.org_nummer = args.hamta_intern; args.intern = True; cmd_hamta(args)
    elif args.finns:
        args.org_nummer = args.finns; cmd_finns(args)
    elif args.sok:
        args.sokterm = args.sok; cmd_sok(args)
    elif args.lagg_till:
        args.json_data = args.lagg_till; cmd_lagg_till(args)
    elif args.uppdatera:
        args.org_nummer = args.uppdatera
        if not args.json_data:
            fel("--uppdatera kräver JSON-data som andra argument")
        cmd_uppdatera(args)
    elif args.ta_bort:
        args.org_nummer = args.ta_bort; cmd_ta_bort(args)
    elif args.aterstall:
        args.org_nummer = args.aterstall; cmd_aterstall(args)
    elif args.koppla:
        args.org_nummer, args.telefon = args.koppla
        cmd_koppla_telefon(args)
    elif args.avkoppla:
        args.org_nummer, args.telefon = args.avkoppla
        cmd_avkoppla_telefon(args)
    elif args.nasta_nr:
        args.org_nummer = args.nasta_nr; cmd_nasta_fakturanummer(args)
    elif args.upd_nasta:
        args.org_nummer = args.upd_nasta[0]
        args.nummer     = int(args.upd_nasta[1])
        cmd_uppdatera_nasta_fakturanummer(args)
    else:
        p.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
