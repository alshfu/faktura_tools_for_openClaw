#!/usr/bin/env python3
"""
onboard_sender.py — Pas-för-pas-registrering av ny avsändare.

Skriptet håller koll på registreringens tillstånd i en temp-fil per telefon.
Varje anrop:
1. Validerar inmatningen
2. Sparar i tillståndsfilen
3. Skickar nästa fråga (eller bekräftelse) via send_template.py
4. Returnerar JSON med vad som hände

Användning:
  --start --till {tel}                          → startar wizard, skickar welcome.txt
  --svar {steg} --varde "..." --till {tel}     → registrerar svar, går till nästa
  --avbryt --till {tel}                         → raderar tillstånd

Steg-ordning:
  1. orgnr     2. name      3. address    4. bank
  5. contact   6. fakturan  7. template   8. confirm
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
    validera_org_nummer, normalisera_org_nummer, formatera_org_nummer,
    validera_epost, formatera_postnummer,
)
from utils.vat import generera_vat


STEG_ORDNING = ["orgnr", "name", "address", "bank", "contact", "fakturan", "template", "confirm"]
STEG_SHABLON = {
    "orgnr":    "sender/ask_orgnr.txt",
    "name":     "sender/ask_name.txt",
    "address":  "sender/ask_address.txt",
    "bank":     "sender/ask_bank.txt",
    "contact":  "sender/ask_contact.txt",
    "fakturan": "sender/ask_fakturan_nu.txt",
    "template": "sender/ask_template.txt",
    "confirm":  "sender/confirm.txt",
}


def nu_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def tillstand_fil(telefon: str) -> Path:
    safe = telefon.replace("+", "plus").replace(" ", "")
    return TMP_DIR / f"sender_wizard_{safe}.json"


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
    fil = tillstand_fil(telefon)
    fil.unlink(missing_ok=True)


def skicka_shablon(shablon: str, telefon: str, variabler: dict = None) -> bool:
    cmd = [
        "python3", str(MSG_TOOLS / "send_template.py"),
        "--shablon", shablon,
        "--till",    telefon,
    ]
    if variabler:
        cmd += ["--variabler", json.dumps(variabler, ensure_ascii=False)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode == 0


def hamta_design_namn(shablon_id: str) -> str:
    """Slå upp namnet på design-shablonen."""
    r = subprocess.run([
        "python3", str(DB_TOOLS / "db_templates.py"), "--hamta", shablon_id
    ], capture_output=True, text=True)
    try:
        data = json.loads(r.stdout)
        return data.get("shablon", {}).get("namn", shablon_id)
    except Exception:
        return shablon_id


def ok(data=None):
    out = {"status": "ok", "timestamp": nu_iso()}
    if data:
        out.update(data)
    print(json.dumps(out, ensure_ascii=False))


def fel(msg: str):
    print(json.dumps({"status": "fel", "meddelande": msg, "timestamp": nu_iso()},
                     ensure_ascii=False))
    sys.exit(1)


# ── Parsing av användarsvar per steg ──────────────────────────────────────────

def parsa_steg(steg: str, varde: str, tillstand: dict) -> tuple:
    """Returnerar (data_att_lagga_till, felmeddelande_eller_None)."""

    if steg == "orgnr":
        if not validera_org_nummer(varde):
            return None, "Ogiltigt org_nummer. Ange 10 siffror (med eller utan bindestreck)."
        org = formatera_org_nummer(varde)
        return {"org_nummer": org, "moms_nummer": generera_vat(org)}, None

    if steg == "name":
        delar = [d.strip() for d in varde.split(",", 1)]
        result = {"foretag": {"namn": delar[0]}}
        if len(delar) > 1:
            result["foretag"]["tagline"] = delar[1]
        return result, None

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

    if steg == "bank":
        # Tolerant parser — letar nyckelord
        bank = {}
        for rad in varde.replace(",", "\n").split("\n"):
            rad = rad.strip()
            low = rad.lower()
            if low.startswith("bankgiro"):
                bank["bankgiro"] = rad.split(":", 1)[-1].strip()
            elif low.startswith("plusgiro"):
                bank["plusgiro"] = rad.split(":", 1)[-1].strip()
            elif low.startswith("iban"):
                bank["iban"] = rad.split(":", 1)[-1].strip()
            elif low.startswith("bic") or low.startswith("swift"):
                bank["bic"] = rad.split(":", 1)[-1].strip()
            elif rad and not any(rad.lower().startswith(p) for p in ("bank", "plus", "iban", "bic", "swift")):
                # Antagligen bara bankgiro-nummer
                bank.setdefault("bankgiro", rad)
        if not bank:
            return None, "Ingen bankuppgift hittades. Ange åtminstone Bankgiro eller IBAN."
        return {"bank": bank}, None

    if steg == "contact":
        delar = [d.strip() for d in varde.split(",")]
        kontakt = {}
        for d in delar:
            if "@" in d:
                kontakt["epost"] = d
            elif d.startswith("+") or d.replace(" ", "").replace("-", "").isdigit():
                kontakt["telefon"] = d
            elif "." in d:
                kontakt["webb"] = d
        if not kontakt.get("epost"):
            return None, "E-postadress krävs."
        if not validera_epost(kontakt["epost"]):
            return None, "Ogiltig e-postadress."
        return {"kontakt": kontakt}, None

    if steg == "fakturan":
        if varde.strip().lower() in ("hoppa över", "hoppa", "skip", "nej", "no"):
            return {"fakturan_nu": {"aktiverad": False}}, None
        delar = [d.strip() for d in varde.split(",")]
        if len(delar) < 3:
            return None, "Ange miljö, API-nyckel och API-lösenord separerade med komma."
        miljo = delar[0].lower()
        if miljo not in ("sandbox", "produktion", "production"):
            return None, "Miljö måste vara 'sandbox' eller 'produktion'."
        if miljo == "production":
            miljo = "produktion"
        return {"fakturan_nu": {
            "aktiverad":     True,
            "miljo_default": miljo,
            "api_nyckel":    delar[1],
            "api_losenord":  delar[2],
        }}, None

    if steg == "template":
        try:
            siffra = int(varde.strip())
        except ValueError:
            return None, "Ange en siffra mellan 1 och 5."
        if not 1 <= siffra <= 5:
            return None, "Ange en siffra mellan 1 och 5."
        shablon_ids = ["klassisk_svart", "minimalistisk_vit", "elegant_burgund",
                       "modern_bla", "professionell_gron"]
        return {"design": {"shablon_id": shablon_ids[siffra - 1]}}, None

    return None, f"Okänt steg: {steg}"


# ── Kommandon ─────────────────────────────────────────────────────────────────

def cmd_start(args):
    rensa_tillstand(args.telefon)
    tillstand = ladda_tillstand(args.telefon)
    tillstand["aktuellt_steg"] = "welcome"
    spara_tillstand(args.telefon, tillstand)
    skicka_shablon("sender/welcome.txt", args.telefon)
    ok({"meddelande": "Wizard startad", "telefon": args.telefon, "aktuellt_steg": "welcome"})


def cmd_svar(args):
    tillstand = ladda_tillstand(args.telefon)
    nuvarande = tillstand.get("aktuellt_steg", "welcome")

    if nuvarande == "welcome":
        # Användarens svar bör vara "JA" → starta verkligt steg 1
        if args.varde.strip().lower() not in ("ja", "yes", "ok", "okej", "okay", "start"):
            return fel("Vänta — användaren har inte bekräftat start.")
        tillstand["aktuellt_steg"] = "orgnr"
        spara_tillstand(args.telefon, tillstand)
        skicka_shablon(STEG_SHABLON["orgnr"], args.telefon)
        ok({"meddelande": "Wizard startad", "aktuellt_steg": "orgnr"})
        return

    if nuvarande == "confirm":
        # Användaren har bekräftat eller vill ändra
        svar = args.varde.strip().lower()
        if svar in ("ja", "yes", "ok", "spara"):
            return slutfor(args.telefon, tillstand)
        elif svar.startswith("ändra"):
            falt = svar.split(maxsplit=1)[-1] if len(svar.split()) > 1 else ""
            return fel(f"Användaren vill ändra: {falt}. Implementera om-rendering.")
        else:
            return fel("Användarens svar tolkades inte. Vänta på JA, ÄNDRA eller AVBRYT.")

    if nuvarande not in STEG_ORDNING:
        return fel(f"Okänt nuvarande steg: {nuvarande}")

    data, valid_fel = parsa_steg(nuvarande, args.varde, tillstand)
    if valid_fel:
        # Skicka felmeddelandet och be om nytt svar
        subprocess.run([
            "openclaw", "message", "send",
            "--channel", "whatsapp",
            "--target", args.telefon,
            "--message", f"⚠️ {valid_fel}\n\nFörsök igen.",
        ], capture_output=True)
        ok({"meddelande": "Valideringsfel", "fel": valid_fel, "aktuellt_steg": nuvarande})
        return

    # Slå ihop data
    deep_merge(tillstand["data"], data)

    # Gå till nästa steg
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
    """Generera variabler och skicka confirm.txt."""
    d = tillstand["data"]
    foretag = d.get("foretag", {})
    adress  = d.get("adress", {})
    kontakt = d.get("kontakt", {})
    bank    = d.get("bank", {})
    f_nu    = d.get("fakturan_nu", {})
    design  = d.get("design", {})

    design_id = design.get("shablon_id", "klassisk_svart")

    variabler = {
        "namn":          foretag.get("namn", ""),
        "org_nummer":    d.get("org_nummer", ""),
        "moms_nummer":   d.get("moms_nummer", ""),
        "f_skatt":       "Ja" if foretag.get("f_skatt", True) else "Nej",
        "gata":          adress.get("gata", ""),
        "postnummer":    adress.get("postnummer", ""),
        "stad":          adress.get("stad", ""),
        "land":          adress.get("land", "SE"),
        "epost":         kontakt.get("epost", "—"),
        "telefon":       kontakt.get("telefon", "—"),
        "bankgiro":      bank.get("bankgiro", "—"),
        "iban":          bank.get("iban", "—"),
        "bic":           bank.get("bic", "—"),
        "fakturan_nu_status": "✅ Aktiverad" if f_nu.get("aktiverad") else "❌ Ej aktiverad",
        "fakturan_nu_miljo":  f_nu.get("miljo_default", "—"),
        "design_namn":   hamta_design_namn(design_id),
    }
    skicka_shablon("sender/confirm.txt", telefon, variabler)


def slutfor(telefon: str, tillstand: dict):
    """Spara avsändaren till databasen."""
    d = tillstand["data"]
    if not d.get("org_nummer"):
        return fel("Saknar org_nummer — kan inte spara")

    payload = {
        "org_nummer":     d["org_nummer"],
        "foretag":        d.get("foretag", {}),
        "adress":         d.get("adress", {}),
        "kontakt":        d.get("kontakt", {}),
        "bank":           d.get("bank", {}),
        "fakturan_nu":    d.get("fakturan_nu", {}),
        "design":         d.get("design", {}),
    }
    payload["foretag"]["org_nummer"]  = d["org_nummer"]
    payload["foretag"]["moms_nummer"] = d.get("moms_nummer", "")

    r = subprocess.run([
        "python3", str(DB_TOOLS / "db_senders.py"),
        "--lagg-till", json.dumps(payload, ensure_ascii=False)
    ], capture_output=True, text=True)

    try:
        result = json.loads(r.stdout)
    except json.JSONDecodeError:
        return fel(f"Kunde inte spara: {r.stderr or r.stdout}")

    if result.get("status") == "ok":
        # Koppla telefon till avsändaren
        subprocess.run([
            "python3", str(DB_TOOLS / "db_senders.py"),
            "--koppla-telefon", d["org_nummer"], telefon
        ], capture_output=True, text=True)

        rensa_tillstand(telefon)

        subprocess.run([
            "openclaw", "message", "send",
            "--channel", "whatsapp",
            "--target", telefon,
            "--message", f"✅ Registrering klar! {d.get('foretag', {}).get('namn', 'Företaget')} är nu registrerat. Du kan börja skapa fakturor.",
        ], capture_output=True)

        ok({"meddelande": "Registrering klar", "org_nummer": d["org_nummer"]})
    else:
        fel(result.get("meddelande", "Okänt fel vid sparning"))


def cmd_avbryt(args):
    rensa_tillstand(args.telefon)
    subprocess.run([
        "openclaw", "message", "send",
        "--channel", "whatsapp",
        "--target", args.telefon,
        "--message", "❌ Registrering avbruten. Inga uppgifter har sparats.",
    ], capture_output=True)
    ok({"meddelande": "Wizard avbruten", "telefon": args.telefon})


def deep_merge(dest: dict, src: dict):
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dest.get(k), dict):
            deep_merge(dest[k], v)
        else:
            dest[k] = v


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--start",   action="store_true")
    p.add_argument("--svar",    action="store_true")
    p.add_argument("--avbryt",  action="store_true")
    p.add_argument("--till",    required=True, help="WhatsApp-nummer")
    p.add_argument("--varde",   help="Användarens svar för aktuellt steg")
    args = p.parse_args()
    args.telefon = args.till

    if args.start:
        cmd_start(args)
    elif args.svar:
        if not args.varde:
            fel("--svar kräver --varde")
        cmd_svar(args)
    elif args.avbryt:
        cmd_avbryt(args)
    else:
        p.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
