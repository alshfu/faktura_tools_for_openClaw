# Billing System v2 — WhatsApp-baserad bokföring

> Multi-tenant fakturahanteringssystem för OpenClaw + Faktura Constructor.  
> All affärslogik i Python-skript. LLM används endast för konversation.

---

## 🎯 Designprinciper

1. **LLM-oberoende** — alla sammanfattningar, meddelanden och beräkningar görs i skript
2. **Mall-baserad kommunikation** — varje WhatsApp-meddelande kommer från en `.txt`-shablon
3. **Phone → Sender mapping** — telefonnummer avgör vilket bolag man arbetar för
4. **Versionerad datalagring** — varje ändring sparas med tidsstämpel och version
5. **Soft delete** — inget tas bort, bara markeras inaktivt (audit-trail)
6. **5 dizajn-shabloner** + möjlighet till per-fält anpassning
7. **Full faktura-livscykel** — utkast → skapad → skickad → betald / krediterad / borttagen

---

## 📁 Projektstruktur

```
billing-system/
├── tools/
│   ├── db/                    # CRUD för alla register
│   ├── workflow/              # Höga operationer (skapa, skicka, kreditera)
│   ├── onboarding/            # Wizards för nya avsändare/mottagare
│   ├── messaging/             # Mall-baserade WhatsApp-meddelanden
│   └── utils/                 # Hjälpfunktioner (OCR, validering, mapping)
│
├── data/                      # JSON-databaser (skapas automatiskt)
│   ├── senders.json
│   ├── recipients.json
│   ├── invoices.json
│   ├── phone_map.json
│   └── counters.json
│
├── templates/
│   ├── messages/              # WhatsApp-shabloner
│   │   ├── sender/            # Frågor för registrering av avsändare
│   │   ├── recipient/         # Frågor för registrering av mottagare
│   │   ├── invoice/           # Sammanfattning, bekräftelse, kreditering
│   │   └── common/            # Allmänna meddelanden
│   └── design/
│       └── presets.json       # 5 fakturadesigner
│
├── docs/
│   └── ARCHITECTURE.md        # Detaljerad arkitekturbeskrivning
│
├── faktura-service/           # Faktura Constructor (Docker HTTP-tjänst)
│   ├── server.js              # HTTP-server på port 3030
│   ├── renderer.js            # JSON → HTML
│   ├── render-pdf.js          # HTML → PDF via Puppeteer
│   ├── Dockerfile             # Docker-image
│   └── docker-compose.yml
│
├── deploy.sh                  # Master deployment-script (install/update/status)
├── install.sh                 # Bakåtkompatibel wrapper
├── SOUL_fyodor.md             # Fjodors instruktioner
├── USER_fyodor.md             # Användardefinitioner
└── README.md
```

---

## 🚀 Installation

### Förutsättningar

- Ubuntu 22.04+
- Python 3.10+
- OpenClaw 2026.5.3+
- Docker (rekommenderas) eller Node.js 18+ (fallback)

### Ett-rads-installation (från GitHub)

```bash
curl -fsSL https://raw.githubusercontent.com/alshfu/faktura_tools_for_openClaw/main/deploy.sh | bash -s install
```

Skriptet sköter allt automatiskt:
1. Kontrollerar förutsättningar (Python, OpenClaw, Docker/Node)
2. Klonar repo till `~/billing-system/`
3. Installerar Python-beroenden (`requests`)
4. Initierar tomma databaser
5. Bygger och startar Faktura Constructor (Docker eller PM2)
6. Skapar OpenClaw-agenten `fyodor` (eller uppdaterar befintlig)
7. Kopierar SOUL.md och USER.md till workspace
8. Startar om gateway

### Uppdatera systemet

```bash
~/billing-system/deploy.sh update
```

Hämtar senaste version från GitHub, behåller all data och konfiguration, bygger om Docker-image och startar om allt.

### Kontrollera status

```bash
~/billing-system/deploy.sh status
```

Visar status på Faktura Constructor, agenten, workspace-filer, databaser och git-revision.

### Miljövariabler

```bash
AGENT_NAME=fakturabot     ~/billing-system/deploy.sh install   # eget agent-namn
AGENT_MODEL=anthropic/claude-sonnet-4-5   ~/billing-system/deploy.sh install   # annan modell
FAKTURA_PORT=3031         ~/billing-system/deploy.sh install   # annan port
BILLING_INSTALL_DIR=/opt/billing  ~/billing-system/deploy.sh install
```

### Första uppstart — lägg till avsändare och telefon-koppling

```bash
# Lägg till första avsändaren
python3 ~/billing-system/tools/db/db_senders.py --lagg-till '{
  "org_nummer": "559203-2279",
  "foretag":    {"namn": "Jowhar AB"},
  "adress":     {"gata": "Storgatan 1", "postnummer": "111 22", "stad": "Stockholm"},
  "bank":       {"bankgiro": "555-6666"},
  "kontakt":    {"epost": "info@jowhar.se"}
}'

# Koppla telefonnummer till avsändaren
python3 ~/billing-system/tools/db/db_phone_map.py \
  --koppla "+46735272989" "559203-2279" \
  '{"roll": "anstalld", "namn": "Said"}'
```

---

## 🧪 Testflöden

### Test 1 — Skapa faktura manuellt (utan agent)

```bash
# 1. Skapa utkast
python3 ~/billing-system/tools/db/db_invoices.py --skapa-utkast '{
  "avsandare_id": "559203-2279",
  "mottagare_id": "559021-3863",
  "nummer": 1,
  "rader": [
    {"beskrivning": "Konsultation", "antal": 10, "apris": 1500, "enhet": "h", "moms_procent": 25}
  ],
  "referens": "Projekt X",
  "betalningsvillkor_dagar": 30
}'
# → returnerar faktura_id

# 2. Skapa PDF
python3 ~/billing-system/tools/workflow/create_invoice.py --faktura-id {id}

# 3. Skicka PDF till WhatsApp
python3 ~/billing-system/tools/workflow/send_invoice.py \
  --faktura-id {id} --till +79956326096
```

### Test 2 — Kreditera

```bash
python3 ~/billing-system/tools/workflow/credit_invoice.py \
  --original-id {id} --skal "Felaktig fakturering" --till +79956326096
```

### Test 3 — Sender registration wizard

```bash
python3 ~/billing-system/tools/onboarding/onboard_sender.py \
  --start --till +46735272989

# Skriptet skickar select. Användaren svarar via WhatsApp.
# Vid varje svar, kalla:
python3 ~/billing-system/tools/onboarding/onboard_sender.py \
  --svar --varde "JA" --till +46735272989
```

---

## 📚 Dokumentation

- **`docs/ARCHITECTURE.md`** — Detaljerad arkitektur, scheman och flöden
- **`SOUL_fyodor.md`** — Fjodors instruktioner (kopieras till workspace-fyodor/SOUL.md)
- **Faktura Constructor docs** — `~/faktura-service/README.md`

---

## 🔧 CLI-referens

### Database operations

| Verktyg | Användning |
|---------|------------|
| `db_senders.py` | Avsändare (CRUD, telefon-koppling, fakturanummer) |
| `db_recipients.py` | Mottagare (CRUD, statistik per avsändare) |
| `db_invoices.py` | Fakturor (CRUD, status, kreditering) |
| `db_phone_map.py` | Telefon → avsändare-mappning |
| `db_templates.py` | Design-shabloner (5 presets) |

### Workflow

| Verktyg | Användning |
|---------|------------|
| `summarize.py` | Sammanfattning av faktura → WhatsApp |
| `create_invoice.py` | PDF via Faktura Constructor |
| `send_invoice.py` | Skicka PDF till WhatsApp |
| `credit_invoice.py` | Kreditera + skapa PDF + skicka |
| `delete_invoice.py` | Soft delete |

### Onboarding

| Verktyg | Användning |
|---------|------------|
| `identify_sender.py` | FÖRSTA steget vid varje meddelande |
| `onboard_sender.py` | 7-stegs registrering av nytt företag |
| `onboard_recipient.py` | 4-stegs registrering av mottagare |

### Messaging

| Verktyg | Användning |
|---------|------------|
| `send_template.py` | Skickar mall-baserat meddelande till WhatsApp |

### Utils

| Verktyg | Användning |
|---------|------------|
| `ocr.py` | Luhn-kontrollsiffra för OCR |
| `vat.py` | SE-VAT från org_nummer |
| `validator.py` | Validering av org_nummer, e-post, telefon, postnummer |
| `faktura_mapper.py` | Internt schema → Faktura Constructor JSON |

---

## 🎨 Design-shabloner

Fem färdiga PDF-designer i `templates/design/presets.json`:

| ID | Namn | Profil |
|----|------|--------|
| `klassisk_svart` | Klassisk Svart | Tidlös, brunröd accent (default) |
| `minimalistisk_vit` | Minimalistisk Vit | Modern svart-vit |
| `elegant_burgund` | Elegant Burgund | Premium, kräm + burgund |
| `modern_bla` | Modern Blå | Företagskänsla |
| `professionell_gron` | Professionell Grön | Naturlig, saklig |

Per-fält-anpassning sparas i avsändarens `design.anpassningar` och appliceras ovanpå presetens style.

---

## 🔮 Roadmap

Framtida förbättringar (efter version 2):

- [ ] **Merinfo.se-parsing** — autofyll företagsdata från org_nummer
- [ ] **E-postintegration** — skicka faktura via SMTP istället för bara Fakturan.nu
- [ ] **Påminnelser** — automatisk uppföljning av obetalda fakturor
- [ ] **Rapporter** — månadssammanfattningar, momsdeklaration
- [ ] **Multi-currency** — EUR, USD för internationella kunder
- [ ] **Mall-editor** — webbgränssnitt för designanpassning
- [ ] **API-export** — Bokio, Visma, Fortnox-integration
