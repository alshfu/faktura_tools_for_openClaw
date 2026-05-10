#!/usr/bin/env python3
"""
db_phone_map.py — CRUD för telefon → avsändare-koppling (phone_map.json).

Detta är det FÖRSTA som agenten kollar vid varje inkommande meddelande.

Användning:
  --lista
  --slag-upp {telefon}
  --koppla {telefon} {avsandare_id} '{roll_data}'
  --avkoppla {telefon}
  --uppdatera-begransningar {telefon} '{partiell}'
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJEKT_ROT = Path(__file__).resolve().parent.parent.parent
DB_PATH     = PROJEKT_ROT / "data" / "phone_map.json"


def nu_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ladda() -> dict:
    if DB_PATH.exists():
        return json.loads(DB_PATH.read_text(encoding="utf-8"))
    return {"version": 2, "uppdaterad": nu_iso(), "kopplingar": {}}


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


# ── Kommandon ─────────────────────────────────────────────────────────────────

def cmd_lista(args):
    db = ladda()
    rader = [{"telefon": tel, **info} for tel, info in db.get("kopplingar", {}).items()]
    ok({"antal": len(rader), "kopplingar": rader})


def cmd_slag_upp(args):
    db = ladda()
    tel = args.telefon
    info = db.get("kopplingar", {}).get(tel)
    if info:
        ok({"telefon": tel, "kanlig": True, **info})
    else:
        # Okänt nummer — defaultar till begränsade rättigheter
        ok({
            "telefon": tel,
            "kanlig":  False,
            "roll":    "okand",
            "avsandare_id": None,
            "begransningar": {
                "endast_fakturor":         True,
                "endast_svenska":          True,
                "kan_se_andra_avsandare":  False,
            },
        })


def cmd_koppla(args):
    try:
        roll_data = json.loads(args.roll_data) if args.roll_data else {}
    except json.JSONDecodeError as e:
        fel(f"Ogiltig JSON: {e}")

    db = ladda()
    db.setdefault("kopplingar", {})

    db["kopplingar"][args.telefon] = {
        "avsandare_id": args.avsandare_id if args.avsandare_id != "null" else None,
        "roll":          roll_data.get("roll", "anstalld"),
        "namn":          roll_data.get("namn", ""),
        "kopplad_datum": nu_iso(),
        "begransningar": roll_data.get("begransningar", {
            "endast_fakturor":         True,
            "endast_svenska":          True,
            "kan_se_andra_avsandare":  False,
        }),
    }
    spara(db)
    ok({"meddelande": "Koppling skapad", "telefon": args.telefon,
        "avsandare_id": args.avsandare_id})


def cmd_avkoppla(args):
    db = ladda()
    if args.telefon not in db.get("kopplingar", {}):
        fel(f"Telefon {args.telefon} finns inte i registret")
    del db["kopplingar"][args.telefon]
    spara(db)
    ok({"meddelande": "Koppling borttagen", "telefon": args.telefon})


def cmd_uppdatera_begransningar(args):
    try:
        partiell = json.loads(args.json_data)
    except json.JSONDecodeError as e:
        fel(f"Ogiltig JSON: {e}")

    db = ladda()
    if args.telefon not in db.get("kopplingar", {}):
        fel(f"Telefon {args.telefon} finns inte i registret")
    db["kopplingar"][args.telefon].setdefault("begransningar", {}).update(partiell)
    db["kopplingar"][args.telefon]["uppdaterad_datum"] = nu_iso()
    spara(db)
    ok({"meddelande": "Begränsningar uppdaterade",
        "telefon": args.telefon,
        "begransningar": db["kopplingar"][args.telefon]["begransningar"]})


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--lista",                  action="store_true")
    p.add_argument("--slag-upp",               metavar="TEL", dest="slag_upp")
    p.add_argument("--koppla",                 nargs=2, metavar=("TEL","AVS"))
    p.add_argument("--avkoppla",               metavar="TEL")
    p.add_argument("--uppdatera-begransningar", metavar="TEL", dest="upd_begr")
    p.add_argument("json_data", nargs="?")
    args = p.parse_args()

    args.roll_data = args.json_data  # alias för koppla

    if args.lista:
        cmd_lista(args)
    elif args.slag_upp:
        args.telefon = args.slag_upp; cmd_slag_upp(args)
    elif args.koppla:
        args.telefon, args.avsandare_id = args.koppla
        cmd_koppla(args)
    elif args.avkoppla:
        args.telefon = args.avkoppla; cmd_avkoppla(args)
    elif args.upd_begr:
        args.telefon = args.upd_begr
        if not args.json_data:
            fel("--uppdatera-begransningar kräver JSON-data")
        cmd_uppdatera_begransningar(args)
    else:
        p.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
