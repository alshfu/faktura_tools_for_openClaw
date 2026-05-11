#!/usr/bin/env python3
"""
tools/config/setup_secrets.py — Interaktiv guide för att sätta API-nycklar

Sparar hemligheter i ~/.billing-system/config.json (mode 0600).
Filen ligger UTANFÖR projektkatalogen och kommer aldrig i git.

Användning:
  python3 setup_secrets.py                  # Alla sektioner
  python3 setup_secrets.py --bara epost
  python3 setup_secrets.py --bara bolagsverket
  python3 setup_secrets.py --bara fakturan_nu
  python3 setup_secrets.py --bara test
  python3 setup_secrets.py --visa           # Visa nuvarande (lösenord maskerade)
  python3 setup_secrets.py --rensa          # Radera allt
"""
import argparse
import getpass
import json
import os
import stat
import sys
from pathlib import Path

CONFIG_DIR  = Path.home() / ".billing-system"
CONFIG_PATH = CONFIG_DIR / "config.json"


# ── Hjälpfunktioner ───────────────────────────────────────────────────────────

def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH) as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_config(data: dict):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_PATH.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp.replace(CONFIG_PATH)
    CONFIG_PATH.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0600


def ask(prompt: str, default: str = "", secret: bool = False) -> str:
    display = f"{prompt}"
    if default:
        masked = "***" if secret else default
        display += f" [{masked}]"
    display += ": "
    try:
        val = getpass.getpass(display) if secret else input(display)
    except (KeyboardInterrupt, EOFError):
        print()
        sys.exit(0)
    return val.strip() or default


def deep_set(d: dict, path: list, value):
    for key in path[:-1]:
        d = d.setdefault(key, {})
    d[path[-1]] = value


def deep_get(d: dict, *path, default="") -> str:
    node = d
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return default
        node = node[key]
    return node or default


def header(title: str):
    print(f"\n{'━' * 50}")
    print(f"  {title}")
    print(f"{'━' * 50}")


def ok(msg: str):  print(f"  ✅ {msg}")
def info(msg: str): print(f"  ℹ  {msg}")
def warn(msg: str): print(f"  ⚠️  {msg}")


# ── Sektioner ─────────────────────────────────────────────────────────────────

def setup_epost(cfg: dict):
    header("E-post (SMTP för utgående fakturor)")
    info("Används när fakturor skickas via e-post direkt från systemet.")
    info("Lämna tomt om du inte använder e-post-utskick.\n")

    cur = cfg.get("epost", {})
    smtp_server = ask("SMTP-server (t.ex. smtp.gmail.com)", deep_get(cur, "smtp_server"))
    smtp_port   = ask("SMTP-port (587 = STARTTLS, 465 = SSL)", deep_get(cur, "smtp_port") or "587")
    login       = ask("E-postadress / login", deep_get(cur, "login"))
    password    = ask("Lösenord / app-lösenord", deep_get(cur, "password"), secret=True)

    cfg["epost"] = {
        "smtp_server": smtp_server,
        "smtp_port":   int(smtp_port) if smtp_port.isdigit() else 587,
        "login":       login,
        "password":    password,
    }
    ok("E-postkonfiguration sparad")


def setup_bolagsverket(cfg: dict):
    header("Bolagsverket API")
    info("Används för autofyll av företagsdata vid registrering.")
    info("Skapa konto på: https://developer.bolagsverket.se\n")

    cur = cfg.get("bolagsverket", {})
    client_id     = ask("CLIENT_ID",     deep_get(cur, "client_id"))
    client_secret = ask("CLIENT_SECRET", deep_get(cur, "client_secret"), secret=True)

    cfg["bolagsverket"] = {
        "client_id":     client_id,
        "client_secret": client_secret,
    }
    ok("Bolagsverket-konfiguration sparad")


def setup_fakturan_nu(cfg: dict):
    header("Fakturan.nu API")
    info("Används för e-postutskick av fakturor via Fakturan.nu.")
    info("Hämta nycklar på: https://www.fakturan.nu/api\n")

    cur = cfg.get("fakturan_nu", {})

    print("  — Sandbox (test) —")
    sb_key  = ask("  API-nyckel (sandbox)",  deep_get(cur, "sandbox", "api_key"))
    sb_pass = ask("  API-lösenord (sandbox)", deep_get(cur, "sandbox", "api_password"), secret=True)

    print("\n  — Produktion —")
    pr_key  = ask("  API-nyckel (produktion)",  deep_get(cur, "produktion", "api_key"))
    pr_pass = ask("  API-lösenord (produktion)", deep_get(cur, "produktion", "api_password"), secret=True)

    cfg["fakturan_nu"] = {
        "sandbox": {
            "api_key":      sb_key,
            "api_password": sb_pass,
        },
        "produktion": {
            "api_key":      pr_key,
            "api_password": pr_pass,
        },
    }
    ok("Fakturan.nu-konfiguration sparad")


def setup_test(cfg: dict):
    header("Testmiljö")
    info("E-postadress som används av automatiska testscenarier (test_suite.py).\n")

    cur = cfg.get("test", {})
    email = ask("E-postadress för tester", deep_get(cur, "email"))

    cfg["test"] = {"email": email}
    ok("Testkonfiguration sparad")


SEKTIONER = {
    "epost":        setup_epost,
    "bolagsverket": setup_bolagsverket,
    "fakturan_nu":  setup_fakturan_nu,
    "test":         setup_test,
}


# ── Kommandon ─────────────────────────────────────────────────────────────────

def cmd_setup(bara: str | None):
    cfg = load_config()

    if bara:
        if bara not in SEKTIONER:
            print(f"Okänd sektion '{bara}'. Välj: {', '.join(SEKTIONER)}")
            sys.exit(1)
        SEKTIONER[bara](cfg)
    else:
        print("\nKonfigurationsguide för Billing System v2")
        print("Tryck Enter för att behålla nuvarande värde. Ctrl+C för att avbryta.\n")
        for fn in SEKTIONER.values():
            fn(cfg)

    save_config(cfg)
    print(f"\n✅ Konfiguration sparad: {CONFIG_PATH} (mode 0600)")

    # Visa saknade fält
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    try:
        from utils.config import Config
        saknas = Config(cfg).missing()
        if saknas:
            warn(f"Fortfarande saknas ({len(saknas)}): {', '.join(saknas)}")
        else:
            ok("Alla obligatoriska fält är ifyllda")
    except Exception:
        pass


def cmd_visa():
    if not CONFIG_PATH.exists():
        print(f"Ingen konfiguration hittad: {CONFIG_PATH}")
        sys.exit(1)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    try:
        from utils.config import Config
        cfg = Config.load()
        cfg_vis = cfg._masked()
        print(json.dumps(cfg_vis, indent=2, ensure_ascii=False))
        saknas = cfg.missing()
        if saknas:
            warn(f"Saknas ({len(saknas)}): {', '.join(saknas)}")
        else:
            ok("Alla obligatoriska fält är ifyllda")
    except Exception as e:
        print(f"Fel: {e}")
        sys.exit(1)


def cmd_rensa():
    if not CONFIG_PATH.exists():
        print("Ingen konfiguration att rensa.")
        return
    try:
        ans = input(f"Radera {CONFIG_PATH}? [j/N] ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print()
        return
    if ans == "j":
        CONFIG_PATH.unlink()
        ok("Konfiguration raderad")
    else:
        info("Avbruten")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description="Konfigurera API-nycklar för Billing System v2")
    p.add_argument("--bara", metavar="SEKTION",
                   help=f"Konfigurera bara en sektion: {', '.join(SEKTIONER)}")
    p.add_argument("--visa",  action="store_true", help="Visa nuvarande konfiguration")
    p.add_argument("--rensa", action="store_true", help="Radera konfigurationsfilen")
    args = p.parse_args()

    if args.visa:
        cmd_visa()
    elif args.rensa:
        cmd_rensa()
    else:
        cmd_setup(args.bara)


if __name__ == "__main__":
    main()
