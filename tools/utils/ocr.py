#!/usr/bin/env python3
"""
ocr.py — Generera svenska OCR-nummer med Luhn-kontrollsiffra.

Användning som modul:
    from utils.ocr import generera_ocr
    ocr = generera_ocr(893)   # → "8932"

Användning som CLI:
    python3 ocr.py 893
"""
import sys


def generera_ocr(faktura_nummer: int) -> str:
    """
    Bygger OCR-nummer från fakturanummer + Luhn-kontrollsiffra.

    Använder vikter 2,1,2,1,... från höger.
    """
    base = str(faktura_nummer)
    total = 0
    for i, ch in enumerate(reversed(base)):
        d = int(ch)
        weight = 2 if i % 2 == 0 else 1
        prod = d * weight
        total += prod if prod < 10 else prod - 9
    check = (10 - (total % 10)) % 10
    return f"{base}{check}"


def validera_ocr(ocr: str) -> bool:
    """Kontrollera om OCR-numret har giltig Luhn-kontrollsiffra."""
    if not ocr.isdigit() or len(ocr) < 2:
        return False
    base = ocr[:-1]
    expected = generera_ocr(int(base))
    return expected == ocr


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Användning: python3 ocr.py <fakturanummer>", file=sys.stderr)
        sys.exit(1)
    try:
        n = int(sys.argv[1])
    except ValueError:
        print("Fakturanummer måste vara heltal", file=sys.stderr)
        sys.exit(1)
    print(generera_ocr(n))
