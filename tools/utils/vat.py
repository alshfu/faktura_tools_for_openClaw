#!/usr/bin/env python3
"""
vat.py — Generera VAT-nummer från svenskt org_nummer.

Regel: SE + org_nummer (utan bindestreck) + 01
Exempel: 559203-2279 → SE559203227901
"""
import re
import sys


def generera_vat(org_nummer: str) -> str:
    rensat = re.sub(r"\D", "", org_nummer or "")
    if len(rensat) != 10:
        raise ValueError(f"Ogiltigt org_nummer: {org_nummer} (måste vara 10 siffror)")
    return f"SE{rensat}01"


def validera_vat(vat: str) -> bool:
    """SE + 10 siffror + 01 = totalt 14 tecken."""
    if not vat:
        return False
    return bool(re.match(r"^SE\d{10}01$", vat.strip().upper()))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Användning: python3 vat.py <org_nummer>", file=sys.stderr)
        sys.exit(1)
    try:
        print(generera_vat(sys.argv[1]))
    except ValueError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
