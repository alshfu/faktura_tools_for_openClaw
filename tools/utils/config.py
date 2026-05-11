#!/usr/bin/env python3
"""
tools/utils/config.py — Läs och validera ~/.billing-system/config.json

Användning:
  python3 config.py --check          # JSON med saknade fält
  python3 config.py --get fakturan_nu sandbox api_key
  python3 config.py --visa           # Visa konfiguration (lösenord maskerade)
"""
import argparse
import json
import os
import sys
from pathlib import Path

CONFIG_PATH = Path.home() / ".billing-system" / "config.json"

# Alla obligatoriska nyckelvägar (dot-notation)
REQUIRED_KEYS = [
    ("fakturan_nu", "sandbox",    "api_key"),
    ("fakturan_nu", "sandbox",    "api_password"),
    ("fakturan_nu", "produktion", "api_key"),
    ("fakturan_nu", "produktion", "api_password"),
    ("bolagsverket", "client_id"),
    ("bolagsverket", "client_secret"),
    ("epost", "smtp_server"),
    ("epost", "smtp_port"),
    ("epost", "login"),
    ("epost", "password"),
    ("test", "email"),
]

# Fält vars värde maskeras vid --visa
SECRET_SUFFIXES = ("password", "api_password", "client_secret")


class ConfigError(Exception):
    pass


class Config:
    def __init__(self, data: dict):
        self._data = data

    @classmethod
    def load(cls, required: bool = True) -> "Config":
        if not CONFIG_PATH.exists():
            if required:
                raise ConfigError(f"Konfigurationsfil saknas: {CONFIG_PATH}\nKör: python3 tools/config/setup_secrets.py")
            return cls({})
        try:
            with open(CONFIG_PATH) as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ConfigError(f"Ogiltig JSON i {CONFIG_PATH}: {e}")
        return cls(data)

    def get(self, *path, default=None):
        node = self._data
        for key in path:
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node if node != "" else default

    def missing(self) -> list:
        result = []
        for path in REQUIRED_KEYS:
            val = self.get(*path)
            if val is None or val == "":
                result.append(".".join(path))
        return result

    def _masked(self) -> dict:
        import copy
        def mask(obj):
            if isinstance(obj, dict):
                return {k: ("***" if any(k.endswith(s) for s in SECRET_SUFFIXES) else mask(v))
                        for k, v in obj.items()}
            return obj
        return mask(copy.deepcopy(self._data))


def cmd_check():
    cfg = Config.load(required=False)
    saknas = cfg.missing()
    print(json.dumps({"saknas": saknas, "antal": len(saknas)}, ensure_ascii=False))


def cmd_get(path: list):
    cfg = Config.load(required=True)
    val = cfg.get(*path)
    if val is None:
        print(json.dumps({"status": "fel", "meddelande": f"Nyckel saknas: {'.'.join(path)}"}))
        sys.exit(1)
    print(json.dumps({"status": "ok", "varde": val}, ensure_ascii=False))


def cmd_visa():
    cfg = Config.load(required=True)
    print(json.dumps(cfg._masked(), indent=2, ensure_ascii=False))
    saknas = cfg.missing()
    if saknas:
        print(f"\n⚠️  Saknas ({len(saknas)}):", ", ".join(saknas))
    else:
        print("\n✅ Alla obligatoriska fält är ifyllda")


def main():
    p = argparse.ArgumentParser(description="Hantera ~/.billing-system/config.json")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true", help="Returnera JSON med saknade fält")
    g.add_argument("--get",   nargs="+", metavar="NYCKEL", help="Hämta ett värde (sökväg)")
    g.add_argument("--visa",  action="store_true", help="Visa konfiguration (lösenord maskerade)")
    args = p.parse_args()

    try:
        if args.check:
            cmd_check()
        elif args.get:
            cmd_get(args.get)
        elif args.visa:
            cmd_visa()
    except ConfigError as e:
        print(json.dumps({"status": "fel", "meddelande": str(e)}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
