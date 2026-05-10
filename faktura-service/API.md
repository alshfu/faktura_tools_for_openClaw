# Faktura API

The faktura editor exposes a programmatic API on `window.FakturaAPI`. Use it from the browser console, an external script, or any embed.

## Quick start

```js
// Switch document type to receipt
FakturaAPI.setDocType("kvitto");

// Switch UI language
FakturaAPI.setLocale("en-US");

// Rename a single field
FakturaAPI.setLabel("documentNumber", "Receipt #");

// Replace items
FakturaAPI.set({
  items: [{ title: "Coffee", qty: 2, price: 35 }]
});

// Update a nested field with a dotted path
FakturaAPI.patch("client.name", "Acme AB");

// Import a full JSON document
FakturaAPI.import({
  docType: "offert",
  client: { name: "New Client AB" },
  items: [{ id: 1, title: "Consulting", qty: 10, price: 1500 }]
});

// Export the current state
const json = FakturaAPI.export();
```

## Document types

`docType` controls the heading. Supported values:

| Value         | Default label (sv) | Default label (en) |
|---------------|--------------------|--------------------|
| `faktura`     | Faktura            | Invoice            |
| `kvitto`      | Kvitto             | Receipt            |
| `offert`      | Offert             | Quote              |
| `kreditnota` | Kreditnota         | Credit Note        |
| `proforma`    | Proformafaktura    | Pro Forma Invoice  |

Override the heading text directly:

```js
FakturaAPI.setLabel("faktura", "Räkning");
```

## Multilingual labels

Every visible label is a key in `state.labels`. Provide a partial override at any time:

```js
FakturaAPI.setLabels({
  billTo: "Rechnung an",
  from:   "Von",
  total:  "Zu zahlen",
  vat:    "MwSt"
});
```

Or load a built-in language pack:

```js
FakturaAPI.setLocale("en-US"); // or "sv-SE"
```

All label keys:

```
faktura, kvitto, offert, kreditnota, proforma,
documentNumber, issuedDate, dueDate, paymentTerms, currency, reference,
billTo, from, attn, orgNumber, vatNumber,
description, quantity, unitPrice, amount, rowNumber,
subtotal, vat, total, totalDue,
bankgiro, ocr, iban, bic, bank, internationalPayment, payment,
paymentTermsTitle, companyInfo, fSkatt, notes
```

## Items

Each item supports custom fields and a per-line VAT override:

```js
FakturaAPI.addItem({
  title: "Travel",
  desc:  "Stockholm ↔ Göteborg",
  qty:   1,
  unit:  "trip",
  price: 1495,
  momsRate: 0.06,
  custom: { project: "ACME-2025-01" }
});

FakturaAPI.updateItem(itemId, { price: 1600 });
FakturaAPI.removeItem(itemId);
```

## Totals

```js
const { gross, discount, subtotal, moms, total, lines } = FakturaAPI.totals();
```

`discount`, `discountPct`, and `rounding` are top-level fields applied before VAT.

## Subscriptions

```js
const unsubscribe = FakturaAPI.subscribe((state) => {
  console.log("Document changed:", state);
});
unsubscribe();
```

## Presets

Built-in presets switch docType + locale + labels in one call:

```js
FakturaAPI.preset("invoice-en-US");
FakturaAPI.preset("receipt-sv-SE");
FakturaAPI.preset("quote-sv-SE");
FakturaAPI.preset("credit-sv-SE");
FakturaAPI.preset("proforma-en-US");

FakturaAPI.presets(); // → string[]

// Define your own
FakturaAPI.registerPreset("invoice-de-DE", {
  docType: "faktura",
  locale: "de-DE",
  labels: { faktura: "Rechnung", billTo: "Rechnung an", ... }
});
```

## Full method index

| Method                          | Purpose                                       |
|--------------------------------|------------------------------------------------|
| `get()`                        | Live state (reference)                         |
| `export()`                     | Deep-cloned JSON snapshot                      |
| `import(json)`                 | Replace state with `json` (deep-merged onto defaults) |
| `reset()`                      | Restore defaults                               |
| `totals()`                     | Computed totals + line totals                  |
| `set(patch)`                   | Deep-merge an object patch                     |
| `patch(path, value)`           | Set a single dotted path                       |
| `addItem(item)`                | Append an item (auto-assigns `id`)             |
| `updateItem(id, patch)`        | Update an item by id                           |
| `removeItem(id)`               | Remove an item                                 |
| `label(key)`                   | Read a label                                   |
| `setLabel(key, value)`         | Set one label                                  |
| `setLabels(obj)`               | Merge multiple labels                          |
| `setLocale(locale)`            | Apply a language pack                          |
| `setDocType(type)`             | Change document type                           |
| `preset(name)`                 | Apply a built-in preset                        |
| `presets()`                    | List preset names                              |
| `registerPreset(name, patch)`  | Add a custom preset                            |
| `subscribe(fn)`                | Listen to changes; returns `unsubscribe`       |
| `docTitle()`                   | Current heading text                           |
| `DEFAULTS`                     | The default document object                    |
| `SCHEMA.sv` / `SCHEMA.en`      | Built-in label packs                           |
