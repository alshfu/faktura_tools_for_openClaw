#!/usr/bin/env python3
"""
send_template.py — Skickar mall-baserat meddelande till WhatsApp.

Använder shabloner från templates/messages/ med variabelsubstitution.
Kringgår LLM helt — agenten kallar bara detta skript.

Användning:
  python3 send_template.py --shablon sender/welcome.txt --till +46735272989
  python3 send_template.py --shablon invoice/created.txt --till +46735272989 \\
    --variabler '{"nummer": 893, "brutto": "21 000 SEK", ...}'
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

# Bestäm projektrot baserat på var skriptet ligger
PROJEKT_ROT  = Path(__file__).resolve().parent.parent.parent
SHABLON_ROT  = PROJEKT_ROT / "templates" / "messages"


def ladda_shablon(shablon_namn: str) -> str:
    """Laddar shablon-fil. shablon_namn är relativ sökväg, t.ex. 'sender/welcome.txt'"""
    path = SHABLON_ROT / shablon_namn
    if not path.exists():
        raise FileNotFoundError(f"Shablon hittades inte: {path}")
    return path.read_text(encoding="utf-8")


def substituera(text: str, variabler: dict) -> str:
    """
    Ersätter {nyckel} med värdet ur variabler.
    Felsäker — okända variabler ersätts med tom sträng.
    """
    if not variabler:
        return text

    import re

    def replace(match):
        key = match.group(1).strip()
        return str(variabler.get(key, ""))

    return re.sub(r'\{([^{}]+)\}', replace, text)


def skicka_via_openclaw(meddelande: str, telefon: str) -> tuple:
    """Returnerar (ok: bool, info: str)"""
    cmd = [
        "openclaw", "message", "send",
        "--channel", "whatsapp",
        "--target", telefon,
        "--message", meddelande,
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode == 0 and "Sent via gateway" in r.stdout:
            # Extrahera Message ID
            msg_id = ""
            for tok in r.stdout.split():
                if tok.startswith("3EB") or tok.startswith("3AD"):
                    msg_id = tok.rstrip(".")
                    break
            return True, msg_id
        return False, (r.stderr.strip() or r.stdout.strip())[:300]
    except subprocess.TimeoutExpired:
        return False, "Timeout — openclaw svarade inte inom 30s"
    except FileNotFoundError:
        return False, "openclaw CLI hittades inte i PATH"
    except Exception as e:
        return False, str(e)


def main():
    parser = argparse.ArgumentParser(description="Skicka mallbaserat WhatsApp-meddelande")
    parser.add_argument("--shablon",   required=True,
                        help="Relativ sökväg, t.ex. 'sender/welcome.txt'")
    parser.add_argument("--till",      required=True, help="WhatsApp-nummer")
    parser.add_argument("--variabler", default="{}",
                        help="JSON-objekt med variabler för substitution")
    args = parser.parse_args()

    # Ladda shablon
    try:
        text = ladda_shablon(args.shablon)
    except FileNotFoundError as e:
        print(json.dumps({"status": "fel", "meddelande": str(e)}, ensure_ascii=False))
        sys.exit(1)

    # Substituera variabler
    try:
        variabler = json.loads(args.variabler) if args.variabler else {}
    except json.JSONDecodeError as e:
        print(json.dumps({"status": "fel",
                          "meddelande": f"Ogiltig JSON i --variabler: {e}"},
                         ensure_ascii=False))
        sys.exit(1)

    meddelande = substituera(text, variabler)

    # Skicka
    ok, info = skicka_via_openclaw(meddelande, args.till)

    if ok:
        print(json.dumps({
            "status":     "ok",
            "shablon":    args.shablon,
            "till":       args.till,
            "message_id": info,
            "tecken":     len(meddelande),
        }, ensure_ascii=False))
    else:
        print(json.dumps({
            "status":     "fel",
            "meddelande": info,
            "shablon":    args.shablon,
            "till":       args.till,
        }, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
