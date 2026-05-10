#!/usr/bin/env python3
"""
validator.py — Validering av svenska företagsdata och kontaktuppgifter.

Användning som modul:
    from utils.validator import (
        validera_org_nummer,
        normalisera_org_nummer,
        validera_epost,
        normalisera_telefon,
    )
"""
import re
import sys


def normalisera_org_nummer(org: str) -> str:
    """Tar bort allt utom siffror. 559203-2279 → 5592032279."""
    return re.sub(r"\D", "", org or "")


def validera_org_nummer(org: str) -> bool:
    """Svenskt org_nummer = exakt 10 siffror."""
    return len(normalisera_org_nummer(org)) == 10


def formatera_org_nummer(org: str) -> str:
    """5592032279 → 559203-2279 (med bindestreck efter 6:e siffran)."""
    rensat = normalisera_org_nummer(org)
    if len(rensat) != 10:
        return org
    return f"{rensat[:6]}-{rensat[6:]}"


def validera_epost(epost: str) -> bool:
    if not epost:
        return False
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", epost.strip()))


def normalisera_telefon(tel: str) -> str:
    """Tar bort mellanslag och bindestreck. Behåller + om finns."""
    if not tel:
        return ""
    tel = tel.strip()
    har_plus = tel.startswith("+")
    siffror = re.sub(r"\D", "", tel)
    return ("+" + siffror) if har_plus else siffror


def validera_telefon(tel: str) -> bool:
    """E.164-format: + följt av 8-15 siffror."""
    n = normalisera_telefon(tel)
    return n.startswith("+") and n[1:].isdigit() and 8 <= len(n[1:]) <= 15


def validera_postnummer(pn: str) -> bool:
    """Svenskt postnummer: 5 siffror med eller utan mellanslag (111 23)."""
    rensat = re.sub(r"\s", "", pn or "")
    return rensat.isdigit() and len(rensat) == 5


def formatera_postnummer(pn: str) -> str:
    """11123 → 111 23"""
    rensat = re.sub(r"\s", "", pn or "")
    if len(rensat) == 5:
        return f"{rensat[:3]} {rensat[3:]}"
    return pn


if __name__ == "__main__":
    import argparse, json
    p = argparse.ArgumentParser()
    p.add_argument("--org-nummer", metavar="ORG")
    p.add_argument("--epost",      metavar="EPOST")
    p.add_argument("--telefon",    metavar="TEL")
    p.add_argument("--postnummer", metavar="PN")
    args = p.parse_args()

    resultat = {}
    if args.org_nummer:
        resultat["org_nummer"] = {
            "input":     args.org_nummer,
            "giltig":    validera_org_nummer(args.org_nummer),
            "formaterad": formatera_org_nummer(args.org_nummer),
        }
    if args.epost:
        resultat["epost"] = {"input": args.epost, "giltig": validera_epost(args.epost)}
    if args.telefon:
        resultat["telefon"] = {
            "input":      args.telefon,
            "giltig":     validera_telefon(args.telefon),
            "normaliserad": normalisera_telefon(args.telefon),
        }
    if args.postnummer:
        resultat["postnummer"] = {
            "input":     args.postnummer,
            "giltig":    validera_postnummer(args.postnummer),
            "formaterad": formatera_postnummer(args.postnummer),
        }

    print(json.dumps(resultat, ensure_ascii=False, indent=2))
