#!/usr/bin/env python3
"""get_conversation.py — Hämta och skicka konversationshistorik till ägaren.

Endast tillåtet att skicka resultatet till huvudanvändaren (+79956326096).

Användning:
  python3 get_conversation.py \
    --med "+46735272989" \
    --sedan "7d" \
    --skicka-till +79956326096

  python3 get_conversation.py \
    --med "Volvo" \
    --sedan "2026-05-01" \
    --skicka-till +79956326096

  # Lista aktiva klienter
  python3 get_conversation.py --aktiva-klienter --sedan "7d" --skicka-till +79956326096

Flöde:
  1. Hitta klientens telefon (om --med är ett namn, slå upp i db_recipients och phone_map).
  2. Hämta meddelanden via db_messages.py --lista.
  3. Formatera via templates/messages/common/conversation_summary.txt.
  4. Skicka via tools/messaging/send_template.py till --skicka-till.

Behörighet:
  --skicka-till MÅSTE vara +79956326096 (huvudanvändaren). Annars 403.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

PROJEKT_ROT = Path(os.environ.get("BILLING_ROOT", Path.home() / "billing-system"))
HUVUDAGARE = "+79956326096"

DB_MESSAGES = PROJEKT_ROT / "tools" / "db" / "db_messages.py"
DB_RECIPIENTS = PROJEKT_ROT / "tools" / "db" / "db_recipients.py"
DB_PHONE_MAP = PROJEKT_ROT / "tools" / "db" / "db_phone_map.py"
SEND_TEMPLATE = PROJEKT_ROT / "tools" / "messaging" / "send_template.py"

MAX_TEXT_LANGD = 200  # Trunkera långa meddelanden i WhatsApp-vyn
MAX_MEDDELANDEN_PER_DUMP = 100  # Hårt tak per dump


def _kor(cmd: list[str]) -> dict:
    """Kör ett underskript och returnerar tolkad JSON-utdata.

    Höjer RuntimeError om skriptet ej kan tolkas eller exit != 0.
    """
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Timeout vid körning av {cmd[0]}")
    if r.returncode != 0:
        try:
            err = json.loads(r.stderr or r.stdout)
            raise RuntimeError(err.get("fel", r.stderr.strip() or "okänt fel"))
        except json.JSONDecodeError:
            raise RuntimeError(f"Skript misslyckades: {r.stderr.strip()[:200]}")
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"Skript returnerade ogiltig JSON: {r.stdout[:200]}")


def normalisera_telefon(raw: str) -> str:
    """Samma logik som db_messages.normalisera_telefon."""
    s = re.sub(r"[\s\-\(\)]", "", raw.strip())
    if s.startswith("+"):
        return s
    if s.startswith("00"):
        return "+" + s[2:]
    if s.startswith("8") and len(s) == 11:
        return "+7" + s[1:]
    if s.startswith("0") and len(s) >= 9:
        return "+46" + s[1:]
    return "+" + s


def ar_telefon(s: str) -> bool:
    """Kollar om strängen ser ut som ett telefonnummer."""
    s = re.sub(r"[\s\-\(\)\+]", "", s)
    return s.isdigit() and len(s) >= 8


def slå_upp_telefon_via_namn(namn: str) -> str | None:
    """Slår upp telefon från klientnamn via db_recipients."""
    try:
        r = _kor(["python3", str(DB_RECIPIENTS), "--sok", namn])
    except RuntimeError:
        return None
    if not r.get("ok"):
        return None
    mottagare = r.get("mottagare") or r.get("resultat") or []
    if not mottagare:
        return None
    # Ta första träffen och hitta dess telefon
    forsta = mottagare[0]
    return forsta.get("kontakt", {}).get("telefon") or forsta.get("telefon")


def formatera_dump(telefon: str, klientnamn: str | None, meddelanden: list[dict]) -> str:
    """Bygger en kompakt WhatsApp-vänlig sammanfattning."""
    if not meddelanden:
        rubrik = klientnamn or telefon
        return f"📭 Inga meddelanden med {rubrik} i angivet intervall."

    rubrik = klientnamn or telefon
    rader = [f"📜 Konversation med {rubrik} ({telefon})", f"Antal: {len(meddelanden)} meddelanden", ""]

    # Trunkera om för mycket
    if len(meddelanden) > MAX_MEDDELANDEN_PER_DUMP:
        rader.append(f"⚠️ Visar de senaste {MAX_MEDDELANDEN_PER_DUMP} av {len(meddelanden)}")
        meddelanden = meddelanden[-MAX_MEDDELANDEN_PER_DUMP:]
        rader.append("")

    for m in meddelanden:
        # Tidpunkt: kortform HH:MM eller datum HH:MM om annan dag
        tid = m["tidpunkt"][:16].replace("T", " ")
        prefix = "→" if m["riktning"] == "ut" else "←"
        text = m["text"] or ""
        if m.get("mall"):
            text = f"[mall: {m['mall']}] {text}".strip()
        if m.get("media"):
            text = f"[media: {m['media'].get('typ','?')}] {text}".strip()
        if len(text) > MAX_TEXT_LANGD:
            text = text[:MAX_TEXT_LANGD - 1] + "…"
        rader.append(f"{tid} {prefix} {text}")

    return "\n".join(rader)


def formatera_aktiva(klienter: list[dict]) -> str:
    if not klienter:
        return "📭 Inga aktiva klienter i angivet intervall."
    rader = [f"👥 Aktiva klienter: {len(klienter)}", ""]
    for k in klienter[:50]:
        senast = k["senast"][:16].replace("T", " ")
        rader.append(f"{k['telefon']} — in:{k['antal_in']} ut:{k['antal_ut']} (senast {senast})")
    if len(klienter) > 50:
        rader.append(f"… och {len(klienter) - 50} fler.")
    return "\n".join(rader)


def skicka_till_agare(text: str, agare_tel: str) -> None:
    """Skickar färdigformaterad text till ägarens WhatsApp.

    Använder en enkel pass-through-mall som bara skickar texten orörd.
    Mallen som krävs: templates/messages/common/conversation_summary.txt
    """
    var_json = json.dumps({"innehall": text}, ensure_ascii=False)
    cmd = [
        "python3", str(SEND_TEMPLATE),
        "--shablon", "common/conversation_summary.txt",
        "--till", agare_tel,
        "--variabler", var_json,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        raise RuntimeError(f"Kunde inte skicka till ägaren: {r.stderr.strip()[:200]}")


def main():
    p = argparse.ArgumentParser(description="Hämta konversationshistorik")
    p.add_argument("--med", help="Telefonnummer eller klientnamn")
    p.add_argument("--sedan", default="7d", help="Tidsintervall: '7d', '24h' eller ISO-datum")
    p.add_argument("--till", default=None, help="Slutdatum")
    p.add_argument("--max", type=int, default=100, help="Max antal meddelanden")
    p.add_argument("--skicka-till", required=True, help="Ägarens telefon (måste vara +79956326096)")
    p.add_argument("--aktiva-klienter", action="store_true",
                   help="Lista aktiva klienter istället för en specifik konversation")

    args = p.parse_args()

    # Säkerhet: endast huvudägaren får ta emot dumpar
    agare = normalisera_telefon(args.skicka_till)
    if agare != HUVUDAGARE:
        print(json.dumps({"ok": False, "fel": "403 — endast huvudägaren kan ta emot historik"},
                         ensure_ascii=False), file=sys.stderr)
        sys.exit(1)

    try:
        if args.aktiva_klienter:
            r = _kor(["python3", str(DB_MESSAGES), "--aktiva", "--sedan", args.sedan])
            klienter = r.get("klienter", [])
            text = formatera_aktiva(klienter)
            skicka_till_agare(text, agare)
            print(json.dumps({"ok": True, "antal_klienter": len(klienter)}, ensure_ascii=False))
            return

        if not args.med:
            raise RuntimeError("Antingen --med eller --aktiva-klienter krävs")

        # Avgör om --med är telefon eller namn
        klientnamn = None
        if ar_telefon(args.med):
            telefon = normalisera_telefon(args.med)
        else:
            klientnamn = args.med
            telefon = slå_upp_telefon_via_namn(args.med)
            if not telefon:
                raise RuntimeError(f"Hittar ingen klient med namnet '{args.med}'. "
                                   f"Skicka telefonnummer istället.")

        # Hämta meddelanden
        cmd = ["python3", str(DB_MESSAGES), "--lista",
               "--telefon", telefon,
               "--sedan", args.sedan,
               "--max", str(args.max)]
        if args.till:
            cmd += ["--till", args.till]
        r = _kor(cmd)
        meddelanden = r.get("meddelanden", [])

        text = formatera_dump(telefon, klientnamn, meddelanden)
        skicka_till_agare(text, agare)
        print(json.dumps({"ok": True, "antal": len(meddelanden), "telefon": telefon},
                         ensure_ascii=False))

    except RuntimeError as e:
        print(json.dumps({"ok": False, "fel": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
