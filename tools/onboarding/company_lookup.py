#!/usr/bin/env python3
"""
tools/onboarding/company_lookup.py — Hämta företagsdata från Bolagsverket

Returnerar färdig payload för db_senders.py / db_recipients.py.

Användning:
  python3 company_lookup.py --orgnr 559203-2279 --format avsandare
  python3 company_lookup.py --orgnr 559203-2279 --format mottagare
  python3 company_lookup.py --orgnr 559203-2279 --format raw
"""
import argparse
import json
import os
import sys
from pathlib import Path

# ── Sökvägar ──────────────────────────────────────────────────────────────────

PROJEKT_ROT  = Path(__file__).resolve().parents[2]
BV_LIB_DIR   = Path(__file__).resolve().parent / "bolagsverket"

# Lägg till bibliotekssökvägen
sys.path.insert(0, str(BV_LIB_DIR))
sys.path.insert(0, str(PROJEKT_ROT / "tools"))


# ── Hjälpfunktioner ───────────────────────────────────────────────────────────

def ok(payload: dict):
    print(json.dumps({"status": "ok", "payload": payload}, ensure_ascii=False))
    sys.exit(0)


def fel(msg: str):
    print(json.dumps({"status": "fel", "meddelande": msg}, ensure_ascii=False))
    sys.exit(1)


def load_credentials() -> tuple[str, str]:
    """Läs BV-nycklar från config.json. Returnerar (client_id, client_secret) eller ("","")."""
    try:
        from utils.config import Config
        cfg = Config.load(required=False)
        cid = cfg.get("bolagsverket", "client_id") or ""
        sec = cfg.get("bolagsverket", "client_secret") or ""
        return cid, sec
    except Exception:
        return "", ""


def map_avsandare(company) -> dict:
    """Company → partiell avsändare-payload (namn + adress)."""
    payload = {}

    if company.name:
        payload["foretag"] = {"namn": company.name}

    addr = company.address
    if addr and any([addr.street, addr.postal_code, addr.city]):
        payload["adress"] = {
            "gata":       addr.street       or "",
            "postnummer": (addr.postal_code or "").replace(" ", ""),
            "stad":       addr.city         or "",
            "land":       addr.country      or "SE",
        }

    return payload


def map_mottagare(company) -> dict:
    """Company → partiell mottagare-payload (foretag.namn + adress)."""
    payload = {}

    if company.name:
        payload["foretag"] = {"namn": company.name}

    addr = company.address
    if addr and any([addr.street, addr.postal_code, addr.city]):
        payload["adress"] = {
            "gata":       addr.street       or "",
            "postnummer": (addr.postal_code or "").replace(" ", ""),
            "stad":       addr.city         or "",
            "land":       addr.country      or "SE",
        }

    return payload


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description="Hämta företagsdata från Bolagsverket")
    p.add_argument("--orgnr",  required=True, metavar="ORG",
                   help="Organisationsnummer (med eller utan bindestreck)")
    p.add_argument("--format", required=True,
                   choices=["avsandare", "mottagare", "raw"],
                   help="Utdataformat")
    args = p.parse_args()

    # Importera biblioteket
    try:
        from bolagsverket import get_client
        from bolagsverket.exceptions import NotFoundError, BolagsverketError
    except ImportError as e:
        fel(f"Kan inte importera bolagsverket-biblioteket: {e}")

    # Sätt upp nycklar
    client_id, client_secret = load_credentials()
    if client_id:
        os.environ.setdefault("BV_CLIENT_ID",     client_id)
        os.environ.setdefault("BV_CLIENT_SECRET", client_secret)

    # Normalisera org.nr
    orgnr = args.orgnr.replace("-", "").replace(" ", "")

    # Hämta data
    try:
        client  = get_client()   # auto: BV om nycklar finns, annars mackan.eu
        company = client.get_company(orgnr)
    except NotFoundError:
        fel(f"Företag {args.orgnr} hittades inte")
    except BolagsverketError as e:
        fel(f"API-fel: {e}")
    except Exception as e:
        fel(f"Oväntat fel: {e}")

    if args.format == "raw":
        ok(company.to_dict(include_raw=False))
    elif args.format == "avsandare":
        ok(map_avsandare(company))
    else:
        ok(map_mottagare(company))


if __name__ == "__main__":
    main()
