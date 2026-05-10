#!/usr/bin/env python3
"""
onboard_recipient.py — Pas-för-pas-registrering av mottagare.

Kortare än sender-wizard — bara 5 steg.

Användning:
  --start --till {tel}
  --svar --varde "..." --till {tel}
  --avbryt --till {tel}
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJEKT_ROT  = Path(__file__).resolve().parent.parent.parent
DB_TOOLS     = PROJEKT_ROT / "tools" / "db"
MSG_TOOLS    = PROJEKT_ROT / "tools" / "messaging"
TMP_DIR      = Path("/tmp/billing_wizard")
TMP_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(PROJEKT_ROT / "tools"))
from utils.validator import (
    validera_org_nummer, formatera_org_nummer,
    validera_epost, formatera_postnummer,
)


STEG_ORDNING = ["orgnr", "name", "email", "address", "confirm"]
STEG_SHABLON = {
    "orgnr":   "recipient/ask_orgnr.txt",
    "name":    "recipient/ask_name.txt",
    "email":   "recipient/ask_email.txt",
    "address": "recipient/ask_address.txt",
}


def nu_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def tillstand_fil(telefon: str) -> Path:
    safe = telefon.replace("+", "plus").replace(" ", "")
    return TMP_DIR / f"recipient_wizard_{safe}.json"


def ladda_tillstand(telefon: str) -> dict:
    fil = tillstand_fil(telefon)
    if fil.exists():
        return json.loads(fil.read_text(encoding="utf-8"))
    return {"telefon": telefon, "data": {}, "startad": nu_iso()}


def spara_tillstand(telefon: str, data: dict):
    fil = tillstand_fil(telefon)
    data["uppdaterad"] = nu_iso()
    fil.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def rensa_tillstand(telefon: str):
    tillstand_fil(telefon).unlink(missing_ok=True)


def skicka_shablon(shablon: str, telefon: str, variabler: dict = None):
    cmd = ["python3", str(MSG_TOOLS / "send_template.py"),
           "--shablon", shablon, "--till", telefon]
    if variabler:
        cmd += ["--variabler", json.dumps(variabler, ensure_ascii=False)]
    subprocess.run(cmd, capture_output=True)


def skicka_text(telefon: str, text: str):
    subprocess.run([
        "openclaw", "message", "send",
        "--channel", "whatsapp",
        "--target", telefon,
        "--message", text,
    ], capture_output=True)


def ok(data=None):
    out = {"status": "ok", "timestamp": nu_iso()}
    if data:
        out.update(data)
    print(json.dumps(out, ensure_ascii=False))


def fel(msg: str):
    print(json.dumps({"status": "fel", "meddelande": msg, "timestamp": nu_iso()},
                     ensure_ascii=False))
    sys.exit(1)


def parsa_steg(steg: str, varde: str) -> tuple:
    if steg == "orgnr":
        if not validera_org_nummer(varde):
            return None, "Ogiltigt org_nummer. Ange 10 siffror."
        return {"org_nummer": formatera_org_nummer(varde)}, None

    if steg == "name":
        delar = [d.strip() for d in varde.split(",", 1)]
        result = {"foretag": {"namn": delar[0]}}
        if len(delar) > 1:
            result["foretag"]["kontaktperson"] = delar[1]
        return result, None

    if steg == "email":
        if not validera_epost(varde.strip()):
            return None, "Ogiltig e-postadress."
        return {"kontakt": {"epost": varde.strip()}}, None

    if steg == "address":
        delar = [d.strip() for d in varde.split(",")]
        if len(delar) < 3:
            return None, "Ange gata, postnummer och stad separerade med komma."
        return {"adress": {
            "gata":       delar[0],
            "postnummer": formatera_postnummer(delar[1]),
            "stad":       delar[2],
            "land":       "SE",
        }}, None

    return None, f"Okänt steg: {steg}"


def cmd_start(args):
    rensa_tillstand(args.telefon)
    tillstand = ladda_tillstand(args.telefon)
    tillstand["aktuellt_steg"] = "orgnr"
    spara_tillstand(args.telefon, tillstand)
    skicka_shablon(STEG_SHABLON["orgnr"], args.telefon)
    ok({"meddelande": "Mottagar-registrering startad", "aktuellt_steg": "orgnr"})


def cmd_svar(args):
    tillstand = ladda_tillstand(args.telefon)
    nuvarande = tillstand.get("aktuellt_steg", "orgnr")

    if nuvarande == "confirm":
        if args.varde.strip().lower() in ("ja", "yes", "ok", "spara"):
            return slutfor(args.telefon, tillstand)
        return fel("Vänta på JA för att bekräfta.")

    data, valid_fel = parsa_steg(nuvarande, args.varde)
    if valid_fel:
        skicka_text(args.telefon, f"⚠️ {valid_fel}\n\nFörsök igen.")
        ok({"meddelande": "Valideringsfel", "fel": valid_fel})
        return

    deep_merge(tillstand["data"], data)

    idx = STEG_ORDNING.index(nuvarande)
    if idx + 1 < len(STEG_ORDNING):
        nasta = STEG_ORDNING[idx + 1]
        tillstand["aktuellt_steg"] = nasta
        spara_tillstand(args.telefon, tillstand)
        if nasta == "confirm":
            skicka_bekraftelse(args.telefon, tillstand)
        else:
            skicka_shablon(STEG_SHABLON[nasta], args.telefon)
        ok({"meddelande": f"Steg {nuvarande} klart", "nasta_steg": nasta})
    else:
        slutfor(args.telefon, tillstand)


def skicka_bekraftelse(telefon: str, tillstand: dict):
    d = tillstand["data"]
    foretag = d.get("foretag", {})
    adress  = d.get("adress", {})
    kontakt = d.get("kontakt", {})
    msg = (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "✅ *KONTROLLERA MOTTAGAREN*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🏢 *{foretag.get('namn','—')}*\n"
        f"   Org.nr: {d.get('org_nummer','—')}\n"
        f"   Kontakt: {foretag.get('kontaktperson','—')}\n\n"
        f"📍 {adress.get('gata','—')}\n"
        f"   {adress.get('postnummer','')} {adress.get('stad','')}\n\n"
        f"📧 {kontakt.get('epost','—')}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Svara *JA* för att spara\n"
        "eller *AVBRYT* för att kasta."
    )
    skicka_text(telefon, msg)


def slutfor(telefon: str, tillstand: dict):
    d = tillstand["data"]
    if not d.get("org_nummer"):
        return fel("Saknar org_nummer")

    payload = {
        "org_nummer": d["org_nummer"],
        "foretag":    d.get("foretag", {}),
        "adress":     d.get("adress", {}),
        "kontakt":    d.get("kontakt", {}),
    }
    payload["foretag"]["org_nummer"] = d["org_nummer"]

    r = subprocess.run([
        "python3", str(DB_TOOLS / "db_recipients.py"),
        "--lagg-till", json.dumps(payload, ensure_ascii=False)
    ], capture_output=True, text=True)

    try:
        result = json.loads(r.stdout)
    except json.JSONDecodeError:
        return fel(f"Kunde inte spara: {r.stderr or r.stdout}")

    if result.get("status") == "ok":
        rensa_tillstand(telefon)
        skicka_text(telefon, f"✅ Mottagaren {payload['foretag'].get('namn','—')} är sparad.")
        ok({"meddelande": "Mottagare sparad", "org_nummer": d["org_nummer"]})
    else:
        fel(result.get("meddelande", "Okänt fel"))


def cmd_avbryt(args):
    rensa_tillstand(args.telefon)
    skicka_text(args.telefon, "❌ Mottagar-registrering avbruten.")
    ok({"meddelande": "Avbruten"})


def deep_merge(dest: dict, src: dict):
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dest.get(k), dict):
            deep_merge(dest[k], v)
        else:
            dest[k] = v


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--start",  action="store_true")
    p.add_argument("--svar",   action="store_true")
    p.add_argument("--avbryt", action="store_true")
    p.add_argument("--till",   required=True)
    p.add_argument("--varde")
    args = p.parse_args()
    args.telefon = args.till

    if args.start:    cmd_start(args)
    elif args.svar:   
        if not args.varde: fel("--svar kräver --varde")
        cmd_svar(args)
    elif args.avbryt: cmd_avbryt(args)
    else: p.print_help(); sys.exit(1)


if __name__ == "__main__":
    main()
