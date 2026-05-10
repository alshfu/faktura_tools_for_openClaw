#!/usr/bin/env python3
"""
db_templates.py — Läs design-shabloner från templates/design/presets.json.

Användning:
  --lista                  → alla 5 shabloner med metadata
  --hamta {shablon_id}    → en specifik shablon
  --formatera-val          → formatera som textmeny för WhatsApp (1-5)
"""
import argparse
import json
import sys
from pathlib import Path

PROJEKT_ROT = Path(__file__).resolve().parent.parent.parent
PRESETS     = PROJEKT_ROT / "templates" / "design" / "presets.json"


def ladda() -> dict:
    if not PRESETS.exists():
        return {"shabloner": {}}
    return json.loads(PRESETS.read_text(encoding="utf-8"))


def ok(data=None):
    out = {"status": "ok"}
    if data:
        out.update(data)
    print(json.dumps(out, ensure_ascii=False))


def fel(msg: str, kod: int = 1):
    print(json.dumps({"status": "fel", "meddelande": msg}, ensure_ascii=False))
    sys.exit(kod)


def cmd_lista(args):
    db = ladda()
    rader = [
        {
            "id":             sid,
            "namn":           v.get("namn", ""),
            "beskrivning":    v.get("beskrivning", ""),
            "forhandsvisning": v.get("forhandsvisning", ""),
            "huvudfarg":      v.get("style", {}).get("headerBg", ""),
            "font":           v.get("style", {}).get("font", ""),
        }
        for sid, v in db.get("shabloner", {}).items()
    ]
    ok({"antal": len(rader), "shabloner": rader})


def cmd_hamta(args):
    db = ladda()
    if args.shablon_id not in db.get("shabloner", {}):
        fel(f"Shablon hittades inte: {args.shablon_id}")
    ok({"shablon": db["shabloner"][args.shablon_id], "id": args.shablon_id})


def cmd_formatera_val(args):
    """Genererar en mänskligt läsbar lista för WhatsApp."""
    db = ladda()
    rader = []
    for i, (sid, v) in enumerate(db.get("shabloner", {}).items(), 1):
        rader.append({
            "siffra": i,
            "id":     sid,
            "namn":   v.get("namn"),
            "beskrivning": v.get("beskrivning"),
        })
    ok({"alternativ": rader})


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--lista",          action="store_true")
    p.add_argument("--hamta",          metavar="ID")
    p.add_argument("--formatera-val",  action="store_true", dest="format_val")
    args = p.parse_args()

    if args.lista:
        cmd_lista(args)
    elif args.hamta:
        args.shablon_id = args.hamta; cmd_hamta(args)
    elif args.format_val:
        cmd_formatera_val(args)
    else:
        p.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
