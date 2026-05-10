#!/usr/bin/env python3
"""
db_recipients.py — CRUD för mottagarregistret (recipients.json v2).

Mottagare delas mellan flera avsändare. Fältet anvands_av_avsandare[]
spårar vilka som har använt denna mottagare. Statistik uppdateras automatiskt.

Användning:
  --lista
  --hamta {org_nummer}
  --finns {org_nummer}
  --sok "{namn_eller_org}"
  --lagg-till '{json}'
  --uppdatera {org_nummer} '{partiell_json}'
  --ta-bort {org_nummer}
  --aterstall {org_nummer}
  --koppla-avsandare {mottagare_org} {avsandare_org}
  --uppdatera-statistik {org_nummer} {belopp_sek}
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJEKT_ROT = Path(__file__).resolve().parent.parent.parent
DB_PATH     = PROJEKT_ROT / "data" / "recipients.json"

sys.path.insert(0, str(PROJEKT_ROT / "tools"))
from utils.validator import validera_org_nummer, normalisera_org_nummer


def nu_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ladda() -> dict:
    if DB_PATH.exists():
        return json.loads(DB_PATH.read_text(encoding="utf-8"))
    return {"version": 2, "uppdaterad": nu_iso(), "mottagare": {}}


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


def nytt_record(payload: dict) -> dict:
    org     = payload.get("org_nummer", "")
    foretag = payload.get("foretag", {})
    adress  = payload.get("adress", {})
    kontakt = payload.get("kontakt", {})

    return {
        "id": org,
        "version": 1,
        "skapad_datum": nu_iso(),
        "uppdaterad_datum": nu_iso(),
        "aktiv": True,

        "foretag": {
            "namn":         foretag.get("namn", payload.get("namn", "")),
            "org_nummer":   org,
            "kontaktperson": foretag.get("kontaktperson", ""),
        },

        "adress": {
            "gata":       adress.get("gata", ""),
            "postnummer": adress.get("postnummer", ""),
            "stad":       adress.get("stad", ""),
            "land":       adress.get("land", "SE"),
        },

        "kontakt": {
            "epost":   kontakt.get("epost", payload.get("epost", "")),
            "telefon": kontakt.get("telefon", ""),
        },

        "anvands_av_avsandare": payload.get("anvands_av_avsandare", []),

        "statistik": {
            "antal_fakturor":       0,
            "total_belopp_sek":     0.0,
            "senaste_faktura_datum": None,
        },
    }


def deep_merge(dest: dict, src: dict):
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dest.get(k), dict):
            deep_merge(dest[k], v)
        else:
            dest[k] = v


# ── Kommandon ─────────────────────────────────────────────────────────────────

def cmd_lista(args):
    db = ladda()
    rader = [
        {
            "org_nummer":     v["foretag"]["org_nummer"],
            "namn":           v["foretag"]["namn"],
            "aktiv":          v.get("aktiv", True),
            "antal_fakturor": v.get("statistik", {}).get("antal_fakturor", 0),
            "total_sek":      v.get("statistik", {}).get("total_belopp_sek", 0),
        }
        for v in db.get("mottagare", {}).values()
    ]
    ok({"antal": len(rader), "mottagare": rader})


def cmd_hamta(args):
    db = ladda()
    org = args.org_nummer
    if org not in db.get("mottagare", {}):
        fel(f"Mottagare {org} hittades inte")
    ok({"mottagare": db["mottagare"][org]})


def cmd_finns(args):
    db = ladda()
    org = args.org_nummer
    finns = org in db.get("mottagare", {})
    result = {"org_nummer": org, "finns": finns}
    if finns:
        v = db["mottagare"][org]
        result["namn"]  = v["foretag"]["namn"]
        result["aktiv"] = v.get("aktiv", True)
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
            "epost":      v.get("kontakt", {}).get("epost", ""),
            "aktiv":      v.get("aktiv", True),
        }
        for v in db.get("mottagare", {}).values()
        if query in v["foretag"]["namn"].lower()
        or query in v["foretag"]["org_nummer"].lower()
    ]
    ok({"antal": len(treff), "treff": treff})


def cmd_lagg_till(args):
    try:
        payload = json.loads(args.json_data)
    except json.JSONDecodeError as e:
        fel(f"Ogiltig JSON: {e}")

    org = payload.get("org_nummer", "")
    if not org:
        fel("Obligatoriskt fält saknas: org_nummer")
    if not validera_org_nummer(org):
        fel(f"Ogiltigt org_nummer: {org}")

    db = ladda()
    db.setdefault("mottagare", {})

    if org in db["mottagare"]:
        fel(f"Mottagare {org} finns redan. Använd --uppdatera.")

    db["mottagare"][org] = nytt_record(payload)
    spara(db)
    ok({"meddelande": "Mottagare tillagd", "org_nummer": org,
        "namn": db["mottagare"][org]["foretag"]["namn"]})


def cmd_uppdatera(args):
    try:
        partiell = json.loads(args.json_data)
    except json.JSONDecodeError as e:
        fel(f"Ogiltig JSON: {e}")

    db = ladda()
    org = args.org_nummer
    if org not in db.get("mottagare", {}):
        fel(f"Mottagare {org} hittades inte")

    deep_merge(db["mottagare"][org], partiell)
    db["mottagare"][org]["uppdaterad_datum"] = nu_iso()
    db["mottagare"][org]["version"] = db["mottagare"][org].get("version", 1) + 1
    spara(db)
    ok({"meddelande": "Mottagare uppdaterad", "org_nummer": org})


def cmd_ta_bort(args):
    db = ladda()
    org = args.org_nummer
    if org not in db.get("mottagare", {}):
        fel(f"Mottagare {org} hittades inte")
    db["mottagare"][org]["aktiv"] = False
    db["mottagare"][org]["uppdaterad_datum"] = nu_iso()
    spara(db)
    ok({"meddelande": "Mottagare deaktiverad", "org_nummer": org})


def cmd_aterstall(args):
    db = ladda()
    org = args.org_nummer
    if org not in db.get("mottagare", {}):
        fel(f"Mottagare {org} hittades inte")
    db["mottagare"][org]["aktiv"] = True
    db["mottagare"][org]["uppdaterad_datum"] = nu_iso()
    spara(db)
    ok({"meddelande": "Mottagare återställd", "org_nummer": org})


def cmd_koppla_avsandare(args):
    db = ladda()
    m_org = args.mottagare_org
    a_org = args.avsandare_org
    if m_org not in db.get("mottagare", {}):
        fel(f"Mottagare {m_org} hittades inte")
    lista = db["mottagare"][m_org].setdefault("anvands_av_avsandare", [])
    if a_org not in lista:
        lista.append(a_org)
    db["mottagare"][m_org]["uppdaterad_datum"] = nu_iso()
    spara(db)
    ok({"meddelande": "Avsändare kopplad till mottagare",
        "avsandare": a_org, "mottagare": m_org})


def cmd_uppdatera_statistik(args):
    db = ladda()
    org = args.org_nummer
    if org not in db.get("mottagare", {}):
        fel(f"Mottagare {org} hittades inte")
    stat = db["mottagare"][org].setdefault("statistik", {})
    stat["antal_fakturor"]       = stat.get("antal_fakturor", 0) + 1
    stat["total_belopp_sek"]     = round(stat.get("total_belopp_sek", 0) + args.belopp, 2)
    stat["senaste_faktura_datum"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    db["mottagare"][org]["uppdaterad_datum"] = nu_iso()
    spara(db)
    ok({"meddelande": "Statistik uppdaterad", "statistik": stat})


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--lista",     action="store_true")
    p.add_argument("--hamta",     metavar="ORG")
    p.add_argument("--finns",     metavar="ORG")
    p.add_argument("--sok",       metavar="TERM")
    p.add_argument("--lagg-till", metavar="JSON", dest="lagg_till")
    p.add_argument("--uppdatera", metavar="ORG")
    p.add_argument("--ta-bort",   metavar="ORG", dest="ta_bort")
    p.add_argument("--aterstall", metavar="ORG")
    p.add_argument("--koppla-avsandare", nargs=2, metavar=("MOTT","AVS"), dest="koppla")
    p.add_argument("--uppdatera-statistik", nargs=2, metavar=("ORG","BELOPP"), dest="stat")
    p.add_argument("json_data", nargs="?")
    args = p.parse_args()

    if args.lista:
        cmd_lista(args)
    elif args.hamta:
        args.org_nummer = args.hamta; cmd_hamta(args)
    elif args.finns:
        args.org_nummer = args.finns; cmd_finns(args)
    elif args.sok:
        args.sokterm = args.sok; cmd_sok(args)
    elif args.lagg_till:
        args.json_data = args.lagg_till; cmd_lagg_till(args)
    elif args.uppdatera:
        args.org_nummer = args.uppdatera
        if not args.json_data:
            fel("--uppdatera kräver JSON-data")
        cmd_uppdatera(args)
    elif args.ta_bort:
        args.org_nummer = args.ta_bort; cmd_ta_bort(args)
    elif args.aterstall:
        args.org_nummer = args.aterstall; cmd_aterstall(args)
    elif args.koppla:
        args.mottagare_org, args.avsandare_org = args.koppla
        cmd_koppla_avsandare(args)
    elif args.stat:
        args.org_nummer = args.stat[0]
        args.belopp     = float(args.stat[1])
        cmd_uppdatera_statistik(args)
    else:
        p.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
