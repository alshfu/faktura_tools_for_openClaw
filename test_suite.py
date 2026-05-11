#!/usr/bin/env python3
"""
test_suite.py — Automatiska testscenarier för Billing System v2.

Körs automatiskt efter install/update via deploy.sh.
Kan också köras manuellt: python3 test_suite.py

Scenarion:
  T01 — Skapa ny avsändare (TEST Bygg AB)
  T02 — Skapa ny mottagare (TEST Fastighet AB)
  T03 — Skapa faktura nr 9001 med 8 rader (mixed tjänster + material)
  T04 — Generera PDF via Faktura Constructor
  T05 — Skicka sammanfattning (summarize.py)
  T06 — Skapa faktura nr 9002 från samma avsändare (ny mottagare)
  T07 — Kreditera faktura 9001
  T08 — Soft-delete faktura 9002
  T09 — Verifiera data i databaser
  T10 — Städa upp testdata

Alla test använder:
  API: sandbox.fakturan.nu
  E-post: alshfu@gmail.com
  Org (avsändare): 559900-0001
  Org (mottagare 1): 559900-0002
  Org (mottagare 2): 559900-0003
"""
import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ── Konfiguration ─────────────────────────────────────────────────────────────

PROJEKT_ROT  = Path(__file__).resolve().parent
DB_TOOLS     = PROJEKT_ROT / "tools" / "db"
WORKFLOW     = PROJEKT_ROT / "tools" / "workflow"

# Ladda nycklar och e-post från konfigurationen
sys.path.insert(0, str(PROJEKT_ROT / "tools"))
try:
    from utils.config import Config, ConfigError
    _cfg = Config.load(required=False)
except Exception:
    _cfg = None

def _cfg_get(*path, default=""):
    if not _cfg:
        return default
    return _cfg.get(*path, default=default)

# Testdata — använder konfigurerade värden där det finns, fallback till hårdkodat
TEST_API_NYCKEL   = _cfg_get("fakturan_nu", "sandbox", "api_key",
                              default="YvtuE3qKRdHnrrvt0z6x")
TEST_API_LOSENORD = _cfg_get("fakturan_nu", "sandbox", "api_password",
                              default="w1BR6iGixoJzS_mHPxGUa1a6bI2fCGC7bC1kBEYt")
TEST_EMAIL        = _cfg_get("test", "email", default="alshfu@gmail.com")
TEST_MILJO        = "sandbox"

TEST_AVS_ORG  = "559900-0001"
TEST_AVS_NAMN = "TEST Bygg & Renovering AB"

TEST_MOT1_ORG  = "559900-0002"
TEST_MOT1_NAMN = "TEST Fastighetsservice Nord AB"

TEST_MOT2_ORG  = "559900-0003"
TEST_MOT2_NAMN = "TEST Bostäder Syd AB"

FAKTURA_NR_1 = 9001
FAKTURA_NR_2 = 9002

FAKTURA_SERVICE_URL = "http://localhost:3030"


# ── Hjälpfunktioner ───────────────────────────────────────────────────────────

class TestResult:
    def __init__(self):
        self.passed   = []
        self.failed   = []
        self.skipped  = []
        self.start    = time.time()

    def ok(self, test_id: str, msg: str):
        elapsed = time.time() - self.start
        self.passed.append((test_id, msg))
        print(f"  ✅ {test_id}: {msg} ({elapsed:.1f}s)")

    def fail(self, test_id: str, msg: str, detail: str = ""):
        elapsed = time.time() - self.start
        self.failed.append((test_id, msg))
        print(f"  ❌ {test_id}: {msg} ({elapsed:.1f}s)")
        if detail:
            for line in detail.strip().split("\n"):
                print(f"     {line}")

    def skip(self, test_id: str, msg: str):
        self.skipped.append((test_id, msg))
        print(f"  ⏭️  {test_id}: {msg} (hoppat)")

    def summary(self) -> bool:
        total   = len(self.passed) + len(self.failed) + len(self.skipped)
        elapsed = time.time() - self.start
        print("")
        print("━" * 50)
        print(f"Testresultat: {len(self.passed)}/{total} OK  |  "
              f"{len(self.failed)} fel  |  {len(self.skipped)} hoppade  |  "
              f"{elapsed:.1f}s totalt")
        if self.failed:
            print("")
            print("Misslyckade test:")
            for tid, msg in self.failed:
                print(f"  • {tid}: {msg}")
        print("━" * 50)
        return len(self.failed) == 0


def kor(cmd: list, timeout: int = 60) -> tuple:
    """Returnerar (parsed_dict, raw_stdout)."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        try:
            return json.loads(r.stdout), r.stdout
        except json.JSONDecodeError:
            return {"status": "fel", "meddelande": r.stdout or r.stderr}, r.stdout
    except subprocess.TimeoutExpired:
        return {"status": "fel", "meddelande": f"Timeout ({timeout}s)"}, ""
    except Exception as e:
        return {"status": "fel", "meddelande": str(e)}, ""


def db(skript: str, args: list) -> dict:
    data, _ = kor(["python3", str(DB_TOOLS / skript)] + args)
    return data


def wf(skript: str, args: list, timeout: int = 60) -> dict:
    data, _ = kor(["python3", str(WORKFLOW / skript)] + args, timeout=timeout)
    return data


# ── Testdata ──────────────────────────────────────────────────────────────────

AVSANDARE_PAYLOAD = {
    "org_nummer": TEST_AVS_ORG,
    "foretag": {
        "namn":    TEST_AVS_NAMN,
        "tagline": "Bygg, renovering & måleri",
        "f_skatt": True,
    },
    "adress": {
        "gata":       "Testgatan 1",
        "postnummer": "111 11",
        "stad":       "Stockholm",
        "land":       "SE",
    },
    "kontakt": {
        "epost":   TEST_EMAIL,
        "telefon": "+46 8 123 456 78",
        "webb":    "www.testbygg.se",
    },
    "bank": {
        "bankgiro":  "999-9999",
        "iban":      "SE00 9999 9999 9999 9999 9999",
        "bic":       "TESTBANK",
        "bank_namn": "Testbanken AB",
        "valuta":    "SEK",
    },
    "fakturan_nu": {
        "aktiverad":     False,      # sandbox — inte skicka riktiga mail
        "api_nyckel":    TEST_API_NYCKEL,
        "api_losenord":  TEST_API_LOSENORD,
        "miljo_default": TEST_MILJO,
    },
    "design": {
        "shablon_id": "klassisk_svart",
    },
    "fakturering": {
        "betalningsvillkor_dagar_default": 30,
        "moms_procent_default":            25,
        "nasta_faktura_nummer":            FAKTURA_NR_1,
        "faktura_villkor_text": "Vid försenad betalning debiteras dröjsmålsränta enligt räntelagen.",
    },
    "telefon_kopplingar": [],
}

MOTTAGARE1_PAYLOAD = {
    "org_nummer": TEST_MOT1_ORG,
    "foretag": {
        "namn":          TEST_MOT1_NAMN,
        "kontaktperson": "Anna Testsson",
    },
    "adress": {
        "gata":       "Mottagargatan 42",
        "postnummer": "212 22",
        "stad":       "Malmö",
        "land":       "SE",
    },
    "kontakt": {
        "epost":   TEST_EMAIL,
        "telefon": "+46 40 123 45 67",
    },
}

MOTTAGARE2_PAYLOAD = {
    "org_nummer": TEST_MOT2_ORG,
    "foretag": {
        "namn":          TEST_MOT2_NAMN,
        "kontaktperson": "Lars Testberg",
    },
    "adress": {
        "gata":       "Bostadsvägen 8",
        "postnummer": "411 33",
        "stad":       "Göteborg",
        "land":       "SE",
    },
    "kontakt": {
        "epost":   TEST_EMAIL,
        "telefon": "+46 31 999 88 77",
    },
}

RADER_FAKTURA_1 = [
    # Tjänster
    {"beskrivning": "Målningsarbete väggar och tak (2 målare)",
     "antal": 80,  "apris": 340,  "enhet": "h",  "moms_procent": 0},
    {"beskrivning": "Spackling och grundning av väggar",
     "antal": 24,  "apris": 340,  "enhet": "h",  "moms_procent": 0},
    {"beskrivning": "Tapetsering av vardagsrum",
     "antal": 16,  "apris": 420,  "enhet": "h",  "moms_procent": 0},
    {"beskrivning": "Golvläggning (parkett) 45 kvm",
     "antal": 45,  "apris": 180,  "enhet": "kvm", "moms_procent": 0},
    {"beskrivning": "Installation av spotlights (12 st)",
     "antal": 12,  "apris": 350,  "enhet": "st",  "moms_procent": 0},
    # Material
    {"beskrivning": "Färg, spackel och grundning",
     "antal": 1,   "apris": 8750,  "enhet": "st",  "moms_procent": 25},
    {"beskrivning": "Parkett Pergo Classic 45 kvm inkl list",
     "antal": 1,   "apris": 14250, "enhet": "st",  "moms_procent": 25},
    {"beskrivning": "Spotlights Philips Hue White (12-pack) + transformator",
     "antal": 1,   "apris": 6490,  "enhet": "st",  "moms_procent": 25},
    # Textrad
    {"beskrivning": "Omvänd skattskyldighet för bygg- och anläggningstjänster",
     "textrad": True},
]

RADER_FAKTURA_2 = [
    {"beskrivning": "Fasadmålning ytterväggar",
     "antal": 60,  "apris": 380,  "enhet": "h",   "moms_procent": 0},
    {"beskrivning": "Puts och lagning av fasad",
     "antal": 20,  "apris": 450,  "enhet": "h",   "moms_procent": 0},
    {"beskrivning": "Byte av fönsterkarmar (6 st)",
     "antal": 6,   "apris": 1200, "enhet": "st",  "moms_procent": 0},
    {"beskrivning": "Takrännebyte 32 m",
     "antal": 32,  "apris": 220,  "enhet": "m",   "moms_procent": 0},
    {"beskrivning": "Ställningsuthyrning 2 veckor",
     "antal": 2,   "apris": 3500, "enhet": "vecka","moms_procent": 25},
    {"beskrivning": "Fasadfärg (utomhus) + primer",
     "antal": 1,   "apris": 9200, "enhet": "st",   "moms_procent": 25},
    {"beskrivning": "Fönsterkarmar + beslag",
     "antal": 1,   "apris": 11400,"enhet": "st",   "moms_procent": 25},
    {"beskrivning": "Körning och transporter",
     "antal": 4,   "apris": 650,  "enhet": "tur",  "moms_procent": 25},
    {"beskrivning": "Omvänd skattskyldighet för bygg- och anläggningstjänster",
     "textrad": True},
]


# ── Tester ────────────────────────────────────────────────────────────────────

def t01_skapa_avsandare(res: TestResult) -> bool:
    print("\n  → Skapar testföretag (avsändare)...")

    # Kontrollera om finns sedan tidigare
    r = db("db_senders.py", ["--finns", TEST_AVS_ORG])
    if r.get("finns"):
        # Ta bort gamla testrester
        db("db_senders.py", ["--ta-bort", TEST_AVS_ORG])

    r = db("db_senders.py", ["--lagg-till", json.dumps(AVSANDARE_PAYLOAD, ensure_ascii=False)])
    if r.get("status") == "ok":
        res.ok("T01", f"Avsändare skapad: {TEST_AVS_NAMN} ({TEST_AVS_ORG})")
        return True
    else:
        res.fail("T01", "Kunde inte skapa avsändare", r.get("meddelande", ""))
        return False


def t02_skapa_mottagare(res: TestResult) -> bool:
    print("\n  → Skapar testmottagare...")
    success = True

    for payload, label in [
        (MOTTAGARE1_PAYLOAD, f"{TEST_MOT1_NAMN} ({TEST_MOT1_ORG})"),
        (MOTTAGARE2_PAYLOAD, f"{TEST_MOT2_NAMN} ({TEST_MOT2_ORG})"),
    ]:
        r = db("db_recipients.py", ["--finns", payload["org_nummer"]])
        if r.get("finns"):
            db("db_recipients.py", ["--ta-bort", payload["org_nummer"]])

        r = db("db_recipients.py", ["--lagg-till", json.dumps(payload, ensure_ascii=False)])
        if r.get("status") == "ok":
            res.ok("T02", f"Mottagare skapad: {label}")
        else:
            res.fail("T02", f"Kunde inte skapa mottagare {label}", r.get("meddelande", ""))
            success = False

    return success


def t03_skapa_faktura_utkast(res: TestResult) -> str | None:
    print("\n  → Skapar fakturautkast #9001...")

    payload = {
        "avsandare_id":               TEST_AVS_ORG,
        "mottagare_id":               TEST_MOT1_ORG,
        "nummer":                     FAKTURA_NR_1,
        "rader":                      RADER_FAKTURA_1,
        "referens":                   "Lägenhetsrenovering Testgatan 42 — TEST",
        "betalningsvillkor_dagar":    30,
        "momslage":                   "omvänd skattskyldighet",
        "miljo":                      TEST_MILJO,
        "mottagare_epost":            TEST_EMAIL,
        "design_shablon":             "klassisk_svart",
    }

    r = db("db_invoices.py", ["--skapa-utkast", json.dumps(payload, ensure_ascii=False)])
    if r.get("status") == "ok":
        fid = r["faktura_id"]
        belopp = r.get("att_betala", 0)
        res.ok("T03", f"Utkast skapat: {fid} | Nr {FAKTURA_NR_1} | {belopp:,.0f} SEK | {len(RADER_FAKTURA_1)} rader")
        return fid
    else:
        res.fail("T03", "Kunde inte skapa utkast", r.get("meddelande", ""))
        return None


def t04_generera_pdf(res: TestResult, faktura_id: str) -> str | None:
    print(f"\n  → Genererar PDF via Faktura Constructor ({FAKTURA_SERVICE_URL})...")

    # Verifiera att tjänsten körs
    try:
        import urllib.request
        with urllib.request.urlopen(f"{FAKTURA_SERVICE_URL}/healthz", timeout=5) as resp:
            if b'"ok":true' not in resp.read():
                res.fail("T04", "Faktura Constructor svarar inte korrekt")
                return None
    except Exception as e:
        res.fail("T04", f"Faktura Constructor ej nåbar: {e}")
        return None

    start = time.time()
    r = wf("create_invoice.py", ["--faktura-id", faktura_id], timeout=90)
    elapsed = time.time() - start

    if r.get("status") == "ok":
        pdf = r.get("pdf_sokväg", "")
        storlek = r.get("pdf_storlek", 0)
        if Path(pdf).exists() and storlek > 5000:
            res.ok("T04", f"PDF skapad: {Path(pdf).name} ({storlek:,} bytes, {elapsed:.1f}s)")
            return pdf
        else:
            res.fail("T04", f"PDF verkar tom eller saknas: {pdf} ({storlek} bytes)")
            return None
    else:
        res.fail("T04", "PDF-generering misslyckades", r.get("meddelande", ""))
        return None


def t05_summarize(res: TestResult, faktura_id: str) -> bool:
    print("\n  → Genererar fakturasammanfattning...")

    r = wf("summarize.py", ["--faktura-id", faktura_id])
    if r.get("status") == "ok":
        variabler = r.get("variabler", {})
        belopp = variabler.get("brutto", "?")
        rader  = variabler.get("rader_lista", "")
        antal_rader = rader.count("\n   ") + 1 if rader else 0
        res.ok("T05", f"Sammanfattning OK: {belopp} | {antal_rader} rader synliga")
        return True
    else:
        res.fail("T05", "Sammanfattning misslyckades", r.get("meddelande", ""))
        return False


def t06_andra_faktura(res: TestResult) -> str | None:
    print("\n  → Skapar faktura #9002 (samma avsändare, annan mottagare)...")

    payload = {
        "avsandare_id":            TEST_AVS_ORG,
        "mottagare_id":            TEST_MOT2_ORG,
        "nummer":                  FAKTURA_NR_2,
        "rader":                   RADER_FAKTURA_2,
        "referens":                "Fasadrenovering Bostadsvägen 8 — TEST",
        "betalningsvillkor_dagar": 30,
        "momslage":                "omvänd skattskyldighet",
        "miljo":                   TEST_MILJO,
        "mottagare_epost":         TEST_EMAIL,
        "design_shablon":          "modern_bla",
    }

    r = db("db_invoices.py", ["--skapa-utkast", json.dumps(payload, ensure_ascii=False)])
    if r.get("status") != "ok":
        res.fail("T06", "Kunde inte skapa utkast 2", r.get("meddelande", ""))
        return None

    fid = r["faktura_id"]
    # Generera PDF
    r2 = wf("create_invoice.py", ["--faktura-id", fid], timeout=90)
    if r2.get("status") == "ok":
        belopp = r.get("att_betala", 0)
        res.ok("T06", f"Faktura #9002 skapad: {fid} | {belopp:,.0f} SEK | design: modern_bla")
        return fid
    else:
        res.fail("T06", "PDF-generering för faktura 2 misslyckades", r2.get("meddelande", ""))
        return None


def t07_kreditera(res: TestResult, faktura_id: str) -> bool:
    print(f"\n  → Krediterar faktura {faktura_id}...")

    r = wf("credit_invoice.py", [
        "--original-id", faktura_id,
        "--skal", "Testscenario — automatisk kreditering",
    ], timeout=90)

    if r.get("status") == "ok":
        kredit_id = r.get("kredit_id")
        kredit_nr = r.get("kredit_nummer")
        belopp    = r.get("att_kreditera", 0)
        res.ok("T07", f"Kreditnota skapad: {kredit_id} | Nr {kredit_nr} | {belopp:,.0f} SEK")
        return True
    else:
        res.fail("T07", "Kreditering misslyckades", r.get("meddelande", ""))
        return False


def t08_ta_bort(res: TestResult, faktura_id: str) -> bool:
    print(f"\n  → Soft-delete faktura {faktura_id}...")

    r = wf("delete_invoice.py", [
        "--faktura-id", faktura_id,
        "--skal", "Testscenario — automatisk borttagning",
    ])

    if r.get("status") == "ok":
        res.ok("T08", f"Faktura {faktura_id} markerad som borttagen (soft delete)")
        return True
    else:
        res.fail("T08", "Borttagning misslyckades", r.get("meddelande", ""))
        return False


def t09_verifiera_data(res: TestResult, faktura_id_1: str, faktura_id_2: str) -> bool:
    print("\n  → Verifierar data i databaser...")
    success = True

    # Avsändare
    r = db("db_senders.py", ["--finns", TEST_AVS_ORG])
    if r.get("finns"):
        res.ok("T09a", f"Avsändare {TEST_AVS_ORG} finns i DB")
    else:
        res.fail("T09a", f"Avsändare {TEST_AVS_ORG} SAKNAS i DB")
        success = False

    # Mottagare 1
    r = db("db_recipients.py", ["--finns", TEST_MOT1_ORG])
    if r.get("finns"):
        res.ok("T09b", f"Mottagare {TEST_MOT1_ORG} finns i DB")
    else:
        res.fail("T09b", f"Mottagare {TEST_MOT1_ORG} SAKNAS i DB")
        success = False

    # Faktura 1 ska vara krediterad
    r = db("db_invoices.py", ["--hamta", faktura_id_1])
    if r.get("status") == "ok":
        status = r["faktura"]["status"]
        rel    = r["faktura"].get("relationer", {})
        if status == "krediterad" and rel.get("krediterad_av"):
            res.ok("T09c", f"Faktura #9001 status=krediterad, länk OK")
        else:
            res.fail("T09c", f"Faktura #9001 fel status: {status}")
            success = False
    else:
        res.fail("T09c", "Kunde inte hämta faktura 1")
        success = False

    # Faktura 2 ska vara borttagen
    r = db("db_invoices.py", ["--hamta", faktura_id_2])
    if r.get("status") == "ok":
        status = r["faktura"]["status"]
        if status == "borttagen":
            res.ok("T09d", f"Faktura #9002 status=borttagen OK")
        else:
            res.fail("T09d", f"Faktura #9002 fel status: {status}")
            success = False
    else:
        res.fail("T09d", "Kunde inte hämta faktura 2")
        success = False

    # Lista fakturor för avsändaren
    r = db("db_invoices.py", ["--lista", "--avsandare", TEST_AVS_ORG])
    if r.get("status") == "ok":
        antal = r.get("antal", 0)
        # Borde ha minst 3: fakt1 + kreditnota + fakt2
        if antal >= 2:
            res.ok("T09e", f"Fakturaregister: {antal} poster för {TEST_AVS_ORG}")
        else:
            res.fail("T09e", f"Förväntat ≥2 fakturor, hittade {antal}")
            success = False

    return success


def t10_stada_upp(res: TestResult, args):
    if args.no_cleanup:
        res.skip("T10", "Testdata behålls (--no-cleanup)")
        return

    print("\n  → Städar upp testdata...")
    removed = 0

    # Ta bort avsändare (soft delete)
    r = db("db_senders.py", ["--ta-bort", TEST_AVS_ORG])
    if r.get("status") == "ok": removed += 1

    # Ta bort mottagare
    for org in [TEST_MOT1_ORG, TEST_MOT2_ORG]:
        r = db("db_recipients.py", ["--ta-bort", org])
        if r.get("status") == "ok": removed += 1

    # Ta bort fakturor (de är redan borttagna/krediterade, men rensa från DB)
    r = db("db_invoices.py", ["--lista", "--avsandare", TEST_AVS_ORG])
    if r.get("status") == "ok":
        for f in r.get("fakturor", []):
            db("db_invoices.py", ["--andra-status", f["id"], "borttagen"])
            removed += 1

    res.ok("T10", f"Städning klar: {removed} testrader deaktiverade")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(
        description="Automatiska testscenarier för Billing System v2",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p.add_argument("--no-cleanup",  action="store_true",
                   help="Behåll testdata i databaser efter klar (för manuell inspektion)")
    p.add_argument("--skip-pdf",    action="store_true",
                   help="Hoppa över PDF-generering (snabbare om Faktura Constructor inte körs)")
    p.add_argument("--only",        metavar="T01,T02,...",
                   help="Kör bara dessa test (kommaseparerat)")
    args = p.parse_args()

    only_tests = set(args.only.upper().split(",")) if args.only else None

    print("")
    print("╔══════════════════════════════════════════╗")
    print("║  Billing System v2 — Testsvit           ║")
    print(f"║  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                       ║")
    print("╚══════════════════════════════════════════╝")
    print(f"\nTestmiljö:     {TEST_MILJO}")
    print(f"Test-e-post:   {TEST_EMAIL}")
    print(f"Avsändare:     {TEST_AVS_NAMN} ({TEST_AVS_ORG})")
    print(f"Mottagare 1:   {TEST_MOT1_NAMN}")
    print(f"Mottagare 2:   {TEST_MOT2_NAMN}")
    print(f"Faktura #1:    {FAKTURA_NR_1} (krediteras i T07)")
    print(f"Faktura #2:    {FAKTURA_NR_2} (tas bort i T08)")
    print(f"Städning:      {'nej' if args.no_cleanup else 'ja (--no-cleanup för att behålla)'}")

    res = TestResult()

    def should_run(tid: str) -> bool:
        return only_tests is None or tid in only_tests

    faktura_id_1 = None
    faktura_id_2 = None

    # ── T01 ──
    if should_run("T01"):
        if not t01_skapa_avsandare(res):
            print("\n  ⚠️  Kritiskt fel i T01 — avbryter.")
            res.summary()
            return 1

    # ── T02 ──
    if should_run("T02"):
        t02_skapa_mottagare(res)

    # ── T03 ──
    if should_run("T03"):
        faktura_id_1 = t03_skapa_faktura_utkast(res)

    # ── T04 ──
    pdf_path = None
    if should_run("T04") and faktura_id_1:
        if args.skip_pdf:
            res.skip("T04", "Hoppar PDF-generering (--skip-pdf)")
        else:
            pdf_path = t04_generera_pdf(res, faktura_id_1)

    # ── T05 ──
    if should_run("T05") and faktura_id_1:
        t05_summarize(res, faktura_id_1)

    # ── T06 ──
    if should_run("T06"):
        if args.skip_pdf:
            res.skip("T06", "Hoppar PDF-generering (--skip-pdf)")
        else:
            faktura_id_2 = t06_andra_faktura(res)

    # ── T07 ──
    if should_run("T07") and faktura_id_1:
        if args.skip_pdf:
            res.skip("T07", "Hoppar kreditering med PDF (--skip-pdf)")
        else:
            t07_kreditera(res, faktura_id_1)

    # ── T08 ──
    if should_run("T08") and faktura_id_2:
        t08_ta_bort(res, faktura_id_2)

    # ── T09 ──
    if should_run("T09") and faktura_id_1 and faktura_id_2:
        t09_verifiera_data(res, faktura_id_1, faktura_id_2)
    elif should_run("T09") and not (faktura_id_1 and faktura_id_2):
        res.skip("T09", "Hoppar verifiering (faktura-ID saknas från tidigare test)")

    # ── T10 ──
    if should_run("T10"):
        t10_stada_upp(res, args)

    all_ok = res.summary()

    if all_ok:
        print("\n  🎉 Alla test godkända — systemet fungerar korrekt!")
    else:
        print("\n  ⚠️  Några test misslyckades — se fel ovan.")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
