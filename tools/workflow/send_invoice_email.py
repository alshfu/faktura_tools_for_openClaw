#!/usr/bin/env python3
"""
send_invoice_email.py — Skicka faktura via Fakturan.nu API (e-post).

Skapar klient + faktura i Fakturan.nu och skickar via deras e-posttjänst.
Uppdaterar fakturastatus i lokal DB efter utskick.

Användning:
  python3 send_invoice_email.py --faktura-id {id}
  python3 send_invoice_email.py --faktura-id {id} --miljo sandbox
  python3 send_invoice_email.py --faktura-id {id} --miljo produktion
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

PROJEKT_ROT = Path(__file__).resolve().parent.parent.parent
DB_TOOLS    = PROJEKT_ROT / "tools" / "db"

API_URLS = {
    "sandbox":    "https://sandbox.fakturan.nu/api/v2",
    "produktion": "https://www.fakturan.nu/api/v2",
}


def nu_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ok(data: dict):
    print(json.dumps(data, ensure_ascii=False))
    sys.exit(0)


def fel(msg: str):
    print(json.dumps({"status": "fel", "meddelande": msg}, ensure_ascii=False))
    sys.exit(1)


def kor(cmd: list) -> dict:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    try:
        return json.loads(r.stdout)
    except Exception:
        return {"status": "fel", "raw": r.stdout[:200]}


def load_credentials(avsandare: dict, miljo: str) -> tuple[str, str]:
    fakt = avsandare.get("fakturan_nu", {})
    if not fakt.get("aktiverad", False):
        fel("Fakturan.nu är inte aktiverat för denna avsändare (aktiverad=false)")
    nyckel   = fakt.get("api_nyckel", "")
    losenord = fakt.get("api_losenord", "")
    if not nyckel or not losenord:
        fel("Fakturan.nu api_nyckel eller api_losenord saknas")
    return nyckel, losenord


def find_or_create_client(s: requests.Session, base: str,
                          mottagare: dict, miljo: str) -> int:
    """Hitta eller skapa klient i Fakturan.nu. Returnerar client_id.

    Prioritetsordning:
      1. Cachad fakturan_nu_client_id i lokal DB (per miljö) — inga API-anrop
      2. Sök via ?org_number= filter — uppdaterar cache om hittas
      3. Skapa ny klient — sparar ID i cache
    """
    org         = mottagare.get("org_nummer", "").replace("-", "")
    cache_key   = f"fakturan_nu_client_id_{miljo}"
    cached_id   = mottagare.get(cache_key)

    if cached_id:
        return int(cached_id)

    namn  = mottagare.get("foretag", {}).get("namn", "")
    email = mottagare.get("kontakt", {}).get("epost", "")
    adr   = mottagare.get("adress", {})

    # Sök via API-filter
    r = s.get(f"{base}/clients", params={"org_number": mottagare.get("org_nummer", "")})
    if r.ok:
        for c in r.json().get("data", []):
            if c.get("org_number", "").replace("-", "") == org:
                _cache_client_id(mottagare["org_nummer"], cache_key, c["id"])
                return c["id"]

    # Skapa ny klient
    payload = {
        "company":     namn,
        "email":       email,
        "org_number":  mottagare.get("org_nummer", ""),
        "client_type": "company",
        "address": {
            "street_address": adr.get("gata", ""),
            "zip_code":       adr.get("postnummer", ""),
            "city":           adr.get("stad", ""),
            "country":        adr.get("land", "SE"),
        },
        "settings": {
            "invoice_delivery_method": "email",
            "email_attach_pdf":        True,
            "locale":                  "sv",
            "currency":                "SEK",
        },
    }
    r = s.post(f"{base}/clients", json=payload)
    if not r.ok:
        fel(f"Kunde inte skapa klient i Fakturan.nu: {r.text[:200]}")
    client_id = r.json()["data"]["id"]
    _cache_client_id(mottagare["org_nummer"], cache_key, client_id)
    return client_id


def _cache_client_id(org_nummer: str, cache_key: str, client_id: int):
    """Spara fakturan_nu_client_id i lokal mottagare-DB för framtida anrop."""
    kor(["python3", str(DB_TOOLS / "db_recipients.py"),
         "--uppdatera", org_nummer,
         json.dumps({cache_key: client_id})])


def build_rows(rader: list) -> list:
    """Konvertera interna fakturarader till Fakturan.nu-format."""
    result = []
    for rad in rader:
        if rad.get("textrad"):
            result.append({
                "text":     rad.get("beskrivning", ""),
                "text_row": True,
            })
        else:
            result.append({
                "product_name":  rad.get("beskrivning", ""),
                "amount":        str(rad.get("antal", 1)),
                "product_price": str(rad.get("apris", 0)),
                "product_tax":   rad.get("moms_procent", 25),
                "product_unit":  rad.get("enhet", "st"),
            })
    return result


def create_invoice(s: requests.Session, base: str, faktura: dict, client_id: int) -> int:
    """Skapa faktura i Fakturan.nu. Returnerar invoice_id."""
    avsandare_id = faktura.get("avsandare_id", "")
    payload = {
        "client_id":      client_id,
        "days":           faktura.get("betalningsvillkor_dagar", 30),
        "our_reference":  faktura.get("referens", ""),
        "rows":           build_rows(faktura.get("rader", [])),
    }
    r = s.post(f"{base}/invoices", json=payload)
    if not r.ok:
        fel(f"Kunde inte skapa faktura i Fakturan.nu: {r.text[:200]}")
    return r.json()["data"]["id"]


def main():
    p = argparse.ArgumentParser(description="Skicka faktura via Fakturan.nu e-post")
    p.add_argument("--faktura-id", required=True, metavar="ID", dest="faktura_id")
    p.add_argument("--miljo", default=None, choices=["sandbox", "produktion"],
                   help="Överstyr miljo (standard: avsändarens inställning)")
    args = p.parse_args()

    # 1. Hämta faktura
    r = kor(["python3", str(DB_TOOLS / "db_invoices.py"), "--hamta", args.faktura_id])
    if r.get("status") != "ok":
        fel(f"Faktura hittades inte: {args.faktura_id}")
    faktura = r["faktura"]

    # 2. Hämta avsändare (intern = okrypterade credentials)
    r = kor(["python3", str(DB_TOOLS / "db_senders.py"), "--hamta-intern", faktura["avsandare_id"]])
    if r.get("status") != "ok":
        fel("Avsändare hittades inte")
    avsandare = r["avsandare"]

    # 3. Hämta mottagare
    r = kor(["python3", str(DB_TOOLS / "db_recipients.py"), "--hamta", faktura["mottagare_id"]])
    if r.get("status") != "ok":
        fel("Mottagare hittades inte")
    mottagare = r["mottagare"]

    # 4. Bestäm miljö
    miljo = args.miljo or avsandare.get("fakturan_nu", {}).get("miljo_default", "sandbox")
    base  = API_URLS.get(miljo, API_URLS["sandbox"])

    # 5. Autentisera
    api_key, api_pass = load_credentials(avsandare, miljo)
    session = requests.Session()
    session.auth = (api_key, api_pass)
    session.headers["Content-Type"] = "application/json"

    # 6. Hitta eller skapa klient (använder cache i lokal DB)
    client_id = find_or_create_client(session, base, mottagare, miljo)

    # 7. Skapa faktura i Fakturan.nu
    fnu_invoice_id = create_invoice(session, base, faktura, client_id)

    # 8. Skicka (delivery_method=email explicit per API-docs)
    r = session.post(f"{base}/invoices/{fnu_invoice_id}/send",
                     json={"delivery_method": "email"})
    if not r.ok or r.text.strip() != "OK":
        fel(f"Skickning misslyckades: {r.status_code} {r.text[:200]}")

    # 9. Logga i lokal DB
    skickning_info = {
        "metod":         "fakturan_nu_email",
        "skickad_datum": nu_iso(),
        "miljo":         miljo,
        "fakturan_nu_id": fnu_invoice_id,
        "mottagare_epost": mottagare.get("kontakt", {}).get("epost", ""),
    }
    kor(["python3", str(DB_TOOLS / "db_invoices.py"),
         "--markera-skickad", args.faktura_id,
         json.dumps(skickning_info, ensure_ascii=False)])

    ok({
        "status":          "ok",
        "faktura_id":      args.faktura_id,
        "fakturan_nu_id":  fnu_invoice_id,
        "skickad_till":    mottagare.get("kontakt", {}).get("epost", ""),
        "miljo":           miljo,
        "meddelande":      "Faktura skickad via Fakturan.nu",
    })


if __name__ == "__main__":
    main()
