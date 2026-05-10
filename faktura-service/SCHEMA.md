# Faktura JSON Schema — full key reference

This is the canonical reference for the document JSON consumed by `FakturaAPI` (in-browser) and `renderFaktura(doc)` (the standalone Node/browser renderer).

Every key is **optional** — missing keys are filled in from `DEFAULT_DOC`. Pass a partial object; only what you provide is overridden.

---

## Top-level

| Key            | Type    | Default     | Description |
|----------------|---------|-------------|-------------|
| `docType`      | string  | `"faktura"` | Document type. One of `faktura`, `kvitto`, `offert`, `kreditnota`, `proforma`. Drives the heading via `labels[docType]`. |
| `locale`       | string  | `"sv-SE"`   | BCP-47 locale. Used for number formatting (`toLocaleString`) and the `<html lang>` attribute. Examples: `sv-SE`, `en-US`, `de-DE`, `fr-FR`. |
| `labels`       | object  | sv pack     | Map of label keys to display strings. See **Labels** below. Partial overrides are merged on top of the locale pack. |
| `sender`       | object  | —           | Issuing company. See **Sender**. |
| `client`       | object  | —           | Recipient. See **Client**. |
| `meta`         | object  | —           | Document metadata (number, dates, terms). See **Meta**. |
| `items`        | array   | `[]`        | Line items. See **Items**. |
| `momsRate`     | number  | `0.25`      | Default VAT rate as a decimal (0.25 = 25 %). Used when an item has no `momsRate`. |
| `discount`     | number  | `0`         | Flat discount in document currency, applied before VAT. |
| `discountPct`  | number  | `0`         | Percentage discount (0–100), applied before VAT. |
| `rounding`     | number  | `0`         | Rounding adjustment added to the final total. Negative allowed. |
| `legal`        | object  | —           | Footer legal text. See **Legal**. |
| `style`        | object  | —           | Visual styling (colors, font). See **Style**. |
| `variant`      | string  | `"klassisk"`| (Browser only) Which UI variant to render: `klassisk`, `redaktionell`, `rutnat`, `interaktiv`. The standalone renderer always emits the Klassisk layout. |

---

## Labels

`labels` is a flat map of strings. Every visible piece of UI copy is keyed here so you can localize or rename anything without touching the renderer.

### Document type headings

| Key          | sv default       | en default          |
|--------------|------------------|---------------------|
| `faktura`    | Faktura          | Invoice             |
| `kvitto`     | Kvitto           | Receipt             |
| `offert`     | Offert           | Quote               |
| `kreditnota` | Kreditnota       | Credit Note         |
| `proforma`   | Proformafaktura  | Pro Forma Invoice   |

### Meta block

| Key              | sv default          | en default       |
|------------------|---------------------|------------------|
| `documentNumber` | Fakturanr           | Invoice No.      |
| `issuedDate`     | Fakturadatum        | Issue Date       |
| `dueDate`        | Förfallodag         | Due Date         |
| `paymentTerms`   | Betalningsvillkor   | Payment Terms    |
| `currency`       | Valuta              | Currency         |
| `reference`      | Referens            | Reference        |

### Parties

| Key          | sv default        | en default   |
|--------------|-------------------|--------------|
| `billTo`     | Faktureras till   | Bill To      |
| `from`       | Avsändare         | From         |
| `attn`       | Att               | Attn         |
| `orgNumber`  | Org.nr            | Reg. No.     |
| `vatNumber`  | Momsreg.nr        | VAT No.      |

### Items table

| Key           | sv default     | en default     |
|---------------|----------------|----------------|
| `description` | Beskrivning    | Description    |
| `quantity`    | Antal          | Qty            |
| `unitPrice`   | À-pris         | Unit Price     |
| `amount`      | Summa          | Amount         |
| `rowNumber`   | №              | #              |

### Totals & payment

| Key                    | sv default                 | en default              |
|------------------------|----------------------------|-------------------------|
| `subtotal`             | Delsumma                   | Subtotal                |
| `vat`                  | Moms                       | VAT                     |
| `total`                | Att betala                 | Total Due               |
| `totalDue`             | Att betala senast          | Pay before              |
| `discount`             | Rabatt                     | Discount                |
| `rounding`             | Öresavrundning             | Rounding                |
| `payment`              | Betalning                  | Payment                 |
| `internationalPayment` | Internationell betalning   | International Payment   |
| `bankgiro`             | Bankgiro                   | Bankgiro                |
| `ocr`                  | OCR                        | OCR                     |
| `iban`                 | IBAN                       | IBAN                    |
| `bic`                  | BIC                        | BIC                     |
| `bank`                 | Bank                       | Bank                    |

### Footer

| Key                  | sv default          | en default       |
|----------------------|---------------------|------------------|
| `paymentTermsTitle`  | Betalningsvillkor   | Payment Terms    |
| `companyInfo`        | Företagsuppgifter   | Company Info     |
| `fSkatt`             | F-skattsedel        | F-tax            |
| `notes`              | Anteckningar        | Notes            |

> Add your own keys freely — anything you set in `labels` is available via `FakturaAPI.label(key)`.

---

## Sender

| Key         | Type     | Description |
|-------------|----------|-------------|
| `name`      | string   | Company name. Bold in the header. |
| `tagline`   | string   | Short descriptor under the name (e.g. "Design Studio AB"). |
| `address`   | string[] | Postal address lines. Rendered as `<br>`-joined block. |
| `contact`   | string[] | Email / phone / web. Free-form, displayed as-is. |
| `orgnr`     | string   | Registration number (Sweden: 559123-4567). |
| `momsnr`    | string   | VAT number (Sweden: SE559123456701). |
| `bankgiro`  | string   | Bankgiro account for domestic payment. |
| `iban`      | string   | IBAN for international payment. |
| `bic`       | string   | SWIFT/BIC code. |
| `bank`      | string   | Bank name. |
| `logoUrl`   | string\|null | URL or data URI of a logo image. Currently not rendered by the standalone renderer; reserved for future use. |
| `custom`    | object   | Free-form bag for any additional sender fields you want to round-trip. |

---

## Client

| Key       | Type     | Description |
|-----------|----------|-------------|
| `name`    | string   | Customer's legal name. |
| `attn`    | string   | Recipient line ("Att: Anna A."). |
| `address` | string[] | Postal address lines. |
| `orgnr`   | string   | Customer's registration number. |
| `email`   | string   | Optional email. |
| `phone`   | string   | Optional phone. |
| `custom`  | object   | Free-form bag for extra client fields. |

---

## Meta

| Key              | Type   | Description |
|------------------|--------|-------------|
| `nr`             | string | Document number ("2025-0142"). |
| `issuedShort`    | string | Issue date in `YYYY-MM-DD` (or any string — passed through). |
| `dueShort`       | string | Due date in `YYYY-MM-DD`. |
| `terms`          | string | Free text payment terms ("21 dagar netto"). |
| `ocr`            | string | OCR reference for Swedish payments. |
| `ref`            | string | External reference (PO number, contract id). |
| `currency`       | string | ISO 4217 code ("SEK", "EUR", "USD"). |
| `currencySymbol` | string | Display symbol ("kr", "€", "$"). Rendered after every amount. |
| `custom`         | object | Free-form extra meta. |

---

## Items

`items` is an array. Each item:

| Key        | Type    | Required | Description |
|------------|---------|----------|-------------|
| `id`       | number\|string | yes | Stable identifier. Used by `updateItem` / `removeItem`. |
| `title`    | string  | yes      | Main line text, rendered bold. |
| `desc`     | string  | no       | Description appended after an em-dash. |
| `qty`      | number  | yes      | Quantity. |
| `unit`     | string  | no       | Unit ("tim", "st", "kg"). Rendered after the quantity. |
| `price`    | number  | yes      | Unit price in document currency. |
| `momsRate` | number\|null | no | Per-line VAT rate. Falls back to top-level `momsRate` when null. |
| `custom`   | object  | no       | Free-form per-line fields (project code, cost center, …). |

Computed at render time:

- `line.total = qty * price`
- `gross = Σ line.total`
- `discount = doc.discount + gross * (doc.discountPct / 100)`
- `subtotal = max(0, gross - discount)`
- `moms` (VAT) = sum over lines of `(line.total / gross) * subtotal * (line.momsRate ?? doc.momsRate)`
- `total = subtotal + moms + rounding`

---

## Legal

| Key       | Type   | Description |
|-----------|--------|-------------|
| `payment` | string | Footer text under "Payment Terms". Late-payment policy, etc. |
| `fskatt`  | string | F-tax statement (Sweden-specific). |
| `notes`   | string | Free-form notes. |
| `venue`   | string | Legal venue/jurisdiction. |

---

## Style

| Key           | Type    | Description |
|---------------|---------|-------------|
| `font`        | string  | One of `Geist`, `Inter`, `Instrument Serif`, `Fraunces`, `JetBrains Mono`. |
| `headerBg`    | string  | CSS color for the header band. |
| `headerText`  | string  | CSS color for header text. |
| `contentBg`   | string  | CSS color for the main body. |
| `contentText` | string  | CSS color for body text. |
| `footerBg`    | string  | CSS color for the footer band. |
| `footerText`  | string  | CSS color for footer text. |
| `accent`      | string  | Accent CSS color (currently used by interactive variant only). |
| `showGrain`   | boolean | Adds a paper-grain texture overlay. |

---

# Programmatic usage

## Standalone Node script (recommended for AI agents)

The renderer is a pure-JS UMD module. No build step, no dependencies.

```bash
node render.js doc.json > invoice.html
# or
node render.js doc.json invoice.html
# or stdin
cat doc.json | node render.js > invoice.html
```

Programmatic:

```js
const { renderFaktura, DEFAULT_DOC } = require("./renderer.js");

const doc = {
  docType: "kvitto",
  locale: "en-US",
  sender: { name: "Acme Inc.", orgnr: "12-3456789" },
  client: { name: "Customer LLC" },
  meta:   { nr: "R-0001", issuedShort: "2026-05-10", currencySymbol: "$" },
  items: [
    { id: 1, title: "Coffee", qty: 2, price: 4.5 },
    { id: 2, title: "Pastry", qty: 1, price: 3.5 },
  ],
  momsRate: 0,
};

const html = renderFaktura(doc);
require("fs").writeFileSync("receipt.html", html);
```

`renderFaktura(doc)` returns a **complete, self-contained HTML document** ready to write to disk, serve over HTTP, or pipe to a headless browser for PDF (Puppeteer / Playwright). All CSS is inlined; only Google Fonts are linked externally.

## Browser

```html
<script src="renderer.js"></script>
<script>
  const html = window.renderFaktura(doc);
  document.documentElement.outerHTML = html;
</script>
```

## In-app (the editor)

Inside `Faktura.html`, use `FakturaAPI` — same schema, but with live React rendering and Tweaks-panel integration. See `API.md`.

---

# Minimal example

```json
{
  "docType": "faktura",
  "locale": "sv-SE",
  "sender": { "name": "Acme AB", "orgnr": "556677-8899", "bankgiro": "1234-5678" },
  "client": { "name": "Kund AB" },
  "meta":   { "nr": "2026-0001", "issuedShort": "2026-05-10", "dueShort": "2026-05-31",
              "currencySymbol": "kr" },
  "items": [
    { "id": 1, "title": "Konsultation", "qty": 10, "unit": "tim", "price": 1500 }
  ],
  "momsRate": 0.25
}
```

Run `node render.js example.json > invoice.html` and open it. See `examples/doc.json` for a fuller starter.
