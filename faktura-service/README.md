# Faktura Constructor — Full Documentation

Standalone invoice/receipt/quote generator for headless use from an AI agent on a Linux VPS. Pure JS, no build step, deep customization via JSON.

> **Target environment:** Ubuntu 22.04+ / Node.js 18+ / used from openClaw AI agent on VPS.

---

## 1. What's in the box

| File | Purpose |
|---|---|
| `renderer.js`   | Core renderer. Pure JS UMD module. Takes a JSON doc, returns a complete self-contained HTML string. No deps. |
| `render.js`     | CLI: JSON → HTML file. |
| `render-pdf.js` | CLI + module: JSON → PDF via headless Chromium (Puppeteer). |
| `SCHEMA.md`     | Per-key JSON reference (every field documented). |
| `API.md`        | In-browser `FakturaAPI` reference (for the live editor). |
| `examples/doc.json` | Working starter document. |
| `Faktura.html`  | Interactive design editor (browser only, not for server use). |

Only **`renderer.js`** + **`render-pdf.js`** are needed on the server.

---

## 2. Installation on Ubuntu VPS

```bash
# 1. Node.js 18+ (skip if already installed)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# 2. Chromium dependencies for Puppeteer (headless rendering)
sudo apt install -y \
  ca-certificates fonts-liberation libasound2 libatk-bridge2.0-0 \
  libatk1.0-0 libc6 libcairo2 libcups2 libdbus-1-3 libexpat1 \
  libfontconfig1 libgbm1 libgcc1 libglib2.0-0 libgtk-3-0 libnspr4 \
  libnss3 libpango-1.0-0 libpangocairo-1.0-0 libstdc++6 libx11-6 \
  libx11-xcb1 libxcb1 libxcomposite1 libxcursor1 libxdamage1 \
  libxext6 libxfixes3 libxi6 libxrandr2 libxrender1 libxss1 libxtst6 \
  lsb-release wget xdg-utils

# 3. Project setup
mkdir faktura && cd faktura
# copy renderer.js, render.js, render-pdf.js, examples/doc.json here
npm init -y
npm i puppeteer
```

That's it. No build step, no bundler, no React on the server.

---

## 3. Quick start

### Generate HTML

```bash
node render.js examples/doc.json > invoice.html
```

### Generate PDF

```bash
node render-pdf.js examples/doc.json invoice.pdf
```

### From an agent (programmatic)

```js
// agent.js
const { renderFaktura }   = require("./renderer.js");
const { renderPdf }       = require("./render-pdf.js");

const doc = {
  docType: "faktura",
  locale:  "sv-SE",
  sender:  { name: "Acme AB", orgnr: "556677-8899", bankgiro: "1234-5678" },
  client:  { name: "Kund AB", attn: "Att: Anna A." },
  meta:    { nr: "2026-0001", issuedShort: "2026-05-10",
             dueShort: "2026-05-31", currencySymbol: "kr" },
  items: [
    { id: 1, title: "Konsultation", desc: "Strategi", qty: 12, unit: "tim", price: 1500 },
    { id: 2, title: "Design",       desc: "Identitet", qty: 30, unit: "tim", price: 1250 }
  ],
  momsRate: 0.25
};

// HTML string (in memory)
const html = renderFaktura(doc);

// PDF file
await renderPdf(doc, "/tmp/invoice.pdf");

// PDF buffer (no file)
const pdfBuffer = await renderPdf(doc); // returns Buffer when path omitted
```

---

## 4. Document JSON

Every field is optional. Missing keys are filled in from `DEFAULT_DOC`. For the full per-key reference see **SCHEMA.md**. Summary:

```jsonc
{
  // ── Document type & locale ──────────────────────────────────────────────
  "docType": "faktura",  // faktura | kvitto | offert | kreditnota | proforma
  "locale":  "sv-SE",    // any BCP-47 locale — controls number format + <html lang>

  // ── Labels (full i18n control) ──────────────────────────────────────────
  // Override any visible string. Every label key listed in SCHEMA.md.
  "labels": {
    "faktura":        "Rechnung",
    "billTo":         "Rechnung an",
    "from":           "Von",
    "documentNumber": "Rechnung Nr.",
    "issuedDate":     "Datum",
    "dueDate":        "Fällig",
    "description":    "Beschreibung",
    "quantity":       "Menge",
    "unitPrice":      "Einzelpreis",
    "amount":         "Betrag",
    "subtotal":       "Zwischensumme",
    "vat":            "MwSt",
    "total":          "Zu zahlen"
    // …40+ keys total, see SCHEMA.md
  },

  // ── Issuer (your company) ──────────────────────────────────────────────
  "sender": {
    "name":     "Acme AB",
    "tagline":  "Design Studio",
    "address":  ["Storgatan 1", "111 22 Stockholm"],
    "contact":  ["hello@acme.se", "+46 8 555 01 24"],
    "orgnr":    "556677-8899",
    "momsnr":   "SE556677889901",
    "bankgiro": "1234-5678",
    "iban":     "SE00 1234 5678 9012 3456 7890",
    "bic":      "HANDSESS",
    "bank":     "Handelsbanken",
    "logoUrl":  null,
    "custom":   { }       // anything extra you want to round-trip
  },

  // ── Recipient ──────────────────────────────────────────────────────────
  "client": {
    "name":    "Kund AB",
    "attn":    "Att: Anna Andersson",
    "address": ["Kungsgatan 9", "411 19 Göteborg"],
    "orgnr":   "556001-2233",
    "email":   "anna@kund.se",
    "phone":   "+46 31 ...",
    "custom":  { }
  },

  // ── Document metadata ──────────────────────────────────────────────────
  "meta": {
    "nr":             "2026-0001",
    "issuedShort":    "2026-05-10",
    "dueShort":       "2026-05-31",
    "terms":          "21 dagar netto",
    "ocr":            "20260010001",
    "ref":            "PO-1234",
    "currency":       "SEK",
    "currencySymbol": "kr",   // displayed after every amount
    "custom":         { }
  },

  // ── Line items (unlimited) ─────────────────────────────────────────────
  "items": [
    {
      "id":       1,            // stable id
      "title":    "Konsultation",
      "desc":     "Strategi & workshops",
      "qty":      12,
      "unit":     "tim",        // optional, displayed after qty
      "price":    1500,
      "momsRate": null,         // overrides doc.momsRate when set (e.g. 0.06)
      "custom":   { "project": "ACME-2025-01" }
    }
  ],

  // ── Totals modifiers ───────────────────────────────────────────────────
  "momsRate":    0.25,    // 25 % VAT default
  "discount":    0,       // flat amount before VAT
  "discountPct": 0,       // percent before VAT
  "rounding":    0,       // adjustment added to final total

  // ── Footer legal text ──────────────────────────────────────────────────
  "legal": {
    "payment": "Dröjsmålsränta enligt räntelagen.",
    "fskatt":  "Innehar F-skattsedel.",
    "notes":   "",
    "venue":   ""
  },

  // ── Visual style ───────────────────────────────────────────────────────
  "style": {
    "font":        "Geist",     // Geist | Inter | Instrument Serif | Fraunces | JetBrains Mono
    "headerBg":    "#1a1814",
    "headerText":  "#f3efe6",
    "contentBg":   "#f3efe6",
    "contentText": "#1a1814",
    "footerBg":    "#ebe5d8",
    "footerText":  "#3d3830",
    "accent":      "#7d3a2e",
    "showGrain":   true
  }
}
```

### Computed totals

The renderer computes these from `items` + `momsRate` + `discount*` + `rounding`:

```
line.total = qty × price
gross      = Σ line.total
discount   = doc.discount + gross × (doc.discountPct / 100)
subtotal   = max(0, gross − discount)
moms       = Σ over lines of (lineShare × subtotal × (line.momsRate ?? doc.momsRate))
total      = subtotal + moms + rounding
```

---

## 5. Document types

`docType` swaps the heading via `labels[docType]`:

| docType      | Default heading (sv) | Default (en) |
|--------------|----------------------|--------------|
| `faktura`    | Faktura              | Invoice      |
| `kvitto`     | Kvitto               | Receipt      |
| `offert`     | Offert               | Quote        |
| `kreditnota` | Kreditnota           | Credit Note  |
| `proforma`   | Proformafaktura      | Pro Forma Invoice |

Override the heading directly:

```js
doc.labels.faktura = "Räkning";  // or any string in any language
```

---

## 6. Multilingual usage

Two ways to localize:

**A. Per-doc labels** — provide a partial `labels` map; merged on top of the locale pack.

```js
const doc = {
  locale: "de-DE",
  labels: {
    faktura: "Rechnung", billTo: "Rechnung an", from: "Von",
    documentNumber: "Rechnung Nr.", dueDate: "Fällig",
    description: "Beschreibung", quantity: "Menge",
    unitPrice: "Einzelpreis", amount: "Betrag",
    subtotal: "Zwischensumme", vat: "MwSt", total: "Zu zahlen",
    payment: "Zahlung", bank: "Bank"
  },
  /* … */
};
```

**B. Built-in packs** — `sv-SE` (default) and `en-US` ship inside `renderer.js`. Selecting locale `en-*` auto-loads the EN pack as the base.

For other languages, build your own pack once and reuse:

```js
const DE_LABELS = require("./locales/de.json");
const doc = { locale: "de-DE", labels: DE_LABELS, /* … */ };
```

---

## 7. PDF generation

```js
const { renderPdf } = require("./render-pdf.js");

// File
await renderPdf(doc, "/var/invoices/2026-0001.pdf");

// Buffer (e.g. to attach to email / upload to S3)
const buffer = await renderPdf(doc);

// Custom format
await renderPdf(doc, "out.pdf", {
  format: "Letter",                 // A4 (default) | Letter | Legal | A3 | A5
  margin: { top: "10mm", bottom: "10mm", left: "10mm", right: "10mm" },
  pdf:    { displayHeaderFooter: false, scale: 1 }
});
```

Under the hood: Puppeteer launches headless Chromium → `page.setContent(html)` → waits for `document.fonts.ready` → `page.pdf({ printBackground: true })`. The output is bit-for-bit identical to Chrome's "Save as PDF" because it uses the same print engine.

### Running as root on a VPS

Puppeteer's bundled Chromium refuses to run as root by default. `render-pdf.js` already passes `--no-sandbox --disable-setuid-sandbox`. If you still hit issues:

```bash
# Run as a non-root user (recommended):
sudo adduser --system --group --shell /bin/bash faktura
sudo -u faktura node render-pdf.js doc.json out.pdf
```

---

## 8. Integrating with openClaw agent

### Direct module use (in-process)

```js
// somewhere in your agent's tool registry
const { renderFaktura } = require("./renderer.js");
const { renderPdf }     = require("./render-pdf.js");

async function generateInvoiceTool({ doc, format = "pdf", outPath }) {
  if (format === "html") {
    const html = renderFaktura(doc);
    if (outPath) require("fs").writeFileSync(outPath, html);
    return { html, path: outPath };
  }
  // pdf
  if (outPath) { await renderPdf(doc, outPath); return { path: outPath }; }
  const buf = await renderPdf(doc);
  return { pdfBase64: buf.toString("base64") };
}
```

### As a microservice (HTTP)

If openClaw calls tools via HTTP, wrap it in an Express endpoint:

```js
// server.js
const express = require("express");
const { renderFaktura } = require("./renderer.js");
const { renderPdf }     = require("./render-pdf.js");

const app = express();
app.use(express.json({ limit: "5mb" }));

app.post("/render/html", (req, res) => {
  res.type("html").send(renderFaktura(req.body));
});

app.post("/render/pdf", async (req, res) => {
  const buf = await renderPdf(req.body);
  res.type("application/pdf").send(buf);
});

app.listen(3030, () => console.log("Faktura service on :3030"));
```

Run with PM2 / systemd for persistence:

```bash
sudo npm i -g pm2
pm2 start server.js --name faktura
pm2 save
pm2 startup
```

### As a CLI tool the agent shells out to

```bash
echo '{"docType":"kvitto",...}' | node render-pdf.js - /tmp/out.pdf
```

The agent constructs JSON → pipes it to `node render-pdf.js - <outpath>` → reads the PDF back.

---

## 9. Agent prompt snippet

Drop this into your agent's system prompt so it knows how to build a doc:

```
TOOL: generate_invoice
  Generates a Faktura PDF from a JSON document.
  Required fields: sender.name, client.name, meta.nr, items[].
  Optional: docType (faktura/kvitto/offert/kreditnota/proforma),
            locale, labels (any subset for i18n),
            momsRate, discount, discountPct,
            style (colors + font).
  Returns: { path: string } or { pdfBase64: string }
  See SCHEMA.md for the full field reference.
```

The agent can then assemble a JSON, call the tool, and the PDF is on disk.

---

## 10. Performance notes

- **First call cold-start:** ~1.5 s (Chromium launch). Reuse the browser across calls in a long-lived process to drop that to ~150 ms/PDF.
- **Memory:** Chromium needs ~200 MB. A 1 GB VPS handles it; 512 MB is tight.
- **Concurrency:** open multiple pages from one browser instance instead of multiple browsers. Limit to N pages where N ≤ vCPUs.

Long-lived browser pattern:

```js
const puppeteer = require("puppeteer");
const { renderFaktura } = require("./renderer.js");

let browser;
async function getBrowser() {
  if (!browser) browser = await puppeteer.launch({
    headless: "new", args: ["--no-sandbox", "--disable-setuid-sandbox"],
  });
  return browser;
}
async function renderPdfFast(doc) {
  const page = await (await getBrowser()).newPage();
  try {
    await page.setContent(renderFaktura(doc), { waitUntil: "networkidle0" });
    await page.evaluate(() => document.fonts && document.fonts.ready);
    return await page.pdf({ format: "A4", printBackground: true,
                            margin: { top: 0, right: 0, bottom: 0, left: 0 } });
  } finally { await page.close(); }
}
```

---

## 11. Troubleshooting

| Symptom | Fix |
|---|---|
| Fonts show fallback in PDF | Make sure VPS has outbound HTTPS to `fonts.googleapis.com`. Otherwise self-host fonts and rewrite the `<link>` tag in `renderer.js`. |
| `Failed to launch the browser process` | Install Chromium deps (step 2 above). |
| Empty page / colors missing | Verify `printBackground: true` (it's on by default in `render-pdf.js`). |
| Special chars (åäö) broken | Make sure JSON is UTF-8 encoded. |
| Numbers formatted wrong | Set `locale` correctly (`"sv-SE"` uses spaces, `"en-US"` uses commas). |

---

## 12. File checklist for VPS deploy

Copy to your VPS:

```
faktura/
├── renderer.js          ← required
├── render.js            ← optional (CLI for HTML)
├── render-pdf.js        ← required for PDF
├── package.json         ← with `puppeteer` dep
└── examples/doc.json    ← reference
```

`Faktura.html`, `*.jsx`, `tweaks-panel.jsx` are **editor-only** and not needed on the server.

---

## 13. Reference index

- **SCHEMA.md** — every JSON field documented (types, defaults, descriptions, formulas)
- **API.md** — in-browser `FakturaAPI` (only relevant if you're embedding the live editor)
- **README.md** — this file
