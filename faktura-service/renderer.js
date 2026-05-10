// ─────────────────────────────────────────────────────────────────────────────
// renderer.js — pure JS faktura renderer
//
// Universal module: works in Node.js (CommonJS / ESM) and in the browser.
// Takes a document JSON (or partial — defaults are merged in) and returns a
// complete, self-contained HTML string. No DOM, no React, no build step.
//
// Node usage:
//   const { renderFaktura, DEFAULT_DOC } = require("./renderer.js");
//   const html = renderFaktura(require("./doc.json"));
//   require("fs").writeFileSync("invoice.html", html);
//
// Browser usage:
//   <script src="renderer.js"></script>
//   const html = window.renderFaktura(myDoc);
//
// CLI:
//   node render.js doc.json > invoice.html
// ─────────────────────────────────────────────────────────────────────────────

(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.FakturaRenderer = factory(), Object.assign(root, factory());
})(typeof self !== "undefined" ? self : this, function () {

  // ── Default labels (Swedish) — every key is overridable via doc.labels ────
  const DEFAULT_LABELS_SV = {
    faktura: "Faktura", kvitto: "Kvitto", offert: "Offert",
    kreditnota: "Kreditnota", proforma: "Proformafaktura",
    documentNumber: "Fakturanr", issuedDate: "Fakturadatum",
    dueDate: "Förfallodag", paymentTerms: "Betalningsvillkor",
    currency: "Valuta", reference: "Referens",
    billTo: "Faktureras till", from: "Avsändare", attn: "Att",
    orgNumber: "Org.nr", vatNumber: "Momsreg.nr",
    description: "Beskrivning", quantity: "Antal",
    unitPrice: "À-pris", amount: "Summa", rowNumber: "№",
    subtotal: "Delsumma", vat: "Moms", total: "Att betala", totalDue: "Att betala senast",
    bankgiro: "Bankgiro", ocr: "OCR", iban: "IBAN", bic: "BIC",
    bank: "Bank", internationalPayment: "Internationell betalning", payment: "Betalning",
    paymentTermsTitle: "Betalningsvillkor", companyInfo: "Företagsuppgifter",
    fSkatt: "F-skattsedel", notes: "Anteckningar", discount: "Rabatt", rounding: "Öresavrundning",
  };
  const DEFAULT_LABELS_EN = {
    faktura: "Invoice", kvitto: "Receipt", offert: "Quote",
    kreditnota: "Credit Note", proforma: "Pro Forma Invoice",
    documentNumber: "Invoice No.", issuedDate: "Issue Date",
    dueDate: "Due Date", paymentTerms: "Payment Terms",
    currency: "Currency", reference: "Reference",
    billTo: "Bill To", from: "From", attn: "Attn",
    orgNumber: "Reg. No.", vatNumber: "VAT No.",
    description: "Description", quantity: "Qty",
    unitPrice: "Unit Price", amount: "Amount", rowNumber: "#",
    subtotal: "Subtotal", vat: "VAT", total: "Total Due", totalDue: "Pay before",
    bankgiro: "Bankgiro", ocr: "OCR", iban: "IBAN", bic: "BIC",
    bank: "Bank", internationalPayment: "International Payment", payment: "Payment",
    paymentTermsTitle: "Payment Terms", companyInfo: "Company Info",
    fSkatt: "F-tax", notes: "Notes", discount: "Discount", rounding: "Rounding",
  };

  const DEFAULT_DOC = {
    docType: "faktura",
    locale: "sv-SE",
    labels: DEFAULT_LABELS_SV,
    sender: {
      name: "Lindberg & Co", tagline: "Designstudio AB",
      address: ["Götgatan 78", "116 21 Stockholm", "Sverige"],
      contact: ["studio@lindberg.se", "+46 8 555 01 24", "lindberg.co"],
      orgnr: "559123-4567", momsnr: "SE559123456701",
      bankgiro: "5402-1187", iban: "SE45 5000 0000 0583 9825 7466",
      bic: "ESSESESS", bank: "SEB", logoUrl: null, custom: {},
    },
    client: {
      name: "Nordström Hotels AB",
      attn: "Att: Elin Söderberg",
      address: ["Birger Jarlsgatan 12", "114 34 Stockholm"],
      orgnr: "556782-9914", email: "", phone: "", custom: {},
    },
    meta: {
      nr: "2025-0142", issuedShort: "2025-04-08", dueShort: "2025-04-29",
      terms: "21 dagar netto", ocr: "21040250142", ref: "",
      currency: "SEK", currencySymbol: "kr", custom: {},
    },
    items: [],
    momsRate: 0.25, discount: 0, discountPct: 0, rounding: 0,
    legal: { payment: "", fskatt: "", notes: "", venue: "" },
    style: {
      font: "Geist",
      headerBg: "#1a1814", headerText: "#f3efe6",
      contentBg: "#f3efe6", contentText: "#1a1814",
      footerBg: "#ebe5d8", footerText: "#3d3830",
      accent: "#7d3a2e", showGrain: true,
    },
  };

  // ── helpers ─────────────────────────────────────────────────────────────
  function deepMerge(t, s) {
    if (Array.isArray(s)) return s.slice();
    if (s && typeof s === "object") {
      const o = { ...(t || {}) };
      for (const k of Object.keys(s)) o[k] = deepMerge(t?.[k], s[k]);
      return o;
    }
    return s === undefined ? t : s;
  }
  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }
  function fmt(n, locale) {
    return Number(n || 0).toLocaleString(locale || "sv-SE",
      { maximumFractionDigits: 0 }).replace(/\u00A0/g, " ");
  }
  function computeTotals(doc) {
    const lines = (doc.items || []).map((it) => ({
      ...it, total: (it.qty || 0) * (it.price || 0),
    }));
    const gross = lines.reduce((s, l) => s + l.total, 0);
    const discount = (doc.discount || 0) + gross * ((doc.discountPct || 0) / 100);
    const subtotal = Math.max(0, gross - discount);
    const moms = Math.round(lines.reduce((s, l) => {
      const rate = l.momsRate != null ? l.momsRate : doc.momsRate;
      const lineNet = l.total * (subtotal / (gross || 1));
      return s + lineNet * rate;
    }, 0));
    const total = subtotal + moms + (doc.rounding || 0);
    return { lines, gross, discount, subtotal, moms, total };
  }

  // ── HTML template ───────────────────────────────────────────────────────
  // opts:
  //   fontsHref  - URL/path to a stylesheet that defines the required @font-face
  //                rules. Defaults to Google Fonts CDN. Pass "/fonts/fonts.css"
  //                for self-hosted (offline) rendering.
  //   inlineCss  - string of additional CSS to inline (overrides defaults).
  function renderFaktura(input, opts) {
    opts = opts || {};
    const fontsHref = opts.fontsHref
      || (typeof process !== "undefined" && process.env && process.env.FAKTURA_FONTS_HREF)
      || "https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Geist:wght@300;400;500;600&family=Geist+Mono:wght@400;500&family=Inter:wght@300;400;500;600&family=Fraunces:ital,wght@0,400;0,500;0,600;1,400&family=JetBrains+Mono:wght@400;500&display=swap";
    const d = deepMerge(DEFAULT_DOC, input || {});
    const L = d.labels;
    const C = d.meta.currencySymbol || "kr";
    const t = computeTotals(d);
    const title = L[d.docType] || d.docType;
    const sym = (n) => `${fmt(n, d.locale)} ${esc(C)}`;

    const itemsRows = t.lines.map((l) => `
      <tr>
        <td><b>${esc(l.title || "")}</b>${l.desc ? `<span class="desc"> — ${esc(l.desc)}</span>` : ""}</td>
        <td class="num">${esc(l.qty || 0)}${l.unit ? " " + esc(l.unit) : ""}</td>
        <td class="num">${sym(l.price)}</td>
        <td class="num"><b>${sym(l.total)}</b></td>
      </tr>`).join("");

    const meta = [
      [L.documentNumber, d.meta.nr],
      [L.issuedDate, d.meta.issuedShort],
      [L.dueDate, d.meta.dueShort],
      [L.paymentTerms, d.meta.terms],
    ].map(([k, v]) => `<div><div class="lbl">${esc(k)}</div><div class="val">${esc(v)}</div></div>`).join("");

    const fontStack = {
      "Geist":            `"Geist", -apple-system, sans-serif`,
      "Inter":            `"Inter", -apple-system, sans-serif`,
      "Instrument Serif": `"Instrument Serif", Georgia, serif`,
      "Fraunces":         `"Fraunces", Georgia, serif`,
      "JetBrains Mono":   `"JetBrains Mono", ui-monospace, monospace`,
    }[d.style.font] || `"Geist", -apple-system, sans-serif`;

    return `<!doctype html>
<html lang="${esc(d.locale).slice(0, 2)}">
<head>
<meta charset="utf-8" />
<title>${esc(title)} ${esc(d.meta.nr)}</title>
<link rel="stylesheet" href="${esc(fontsHref)}" />
<style>
  *{box-sizing:border-box} html,body{margin:0;padding:0;background:#e9e3d4}
  body{font-family:${fontStack};font-size:11px;line-height:1.5;color:${esc(d.style.contentText)}}
  .a4{width:794px;min-height:1123px;margin:24px auto;background:${esc(d.style.contentBg)};
    display:flex;flex-direction:column;box-shadow:0 4px 24px rgba(0,0,0,.08)}
  .hdr{background:${esc(d.style.headerBg)};color:${esc(d.style.headerText)};
    padding:32px 60px 28px;display:flex;justify-content:space-between;align-items:flex-start}
  .hdr .name{font-size:26px;letter-spacing:-.02em;line-height:1}
  .hdr .tag{font-size:9.5px;letter-spacing:.14em;text-transform:uppercase;opacity:.7;margin-top:8px}
  .hdr .title{font-family:"Instrument Serif",Georgia,serif;font-style:italic;font-size:46px;
    line-height:1;letter-spacing:-.02em}
  .body{padding:28px 60px;flex:1;display:flex;flex-direction:column}
  .meta{display:grid;grid-template-columns:repeat(4,1fr);gap:24px;padding-bottom:12px;
    border-bottom:1px solid ${esc(d.style.contentText)};margin-bottom:20px}
  .lbl{font-size:9.5px;letter-spacing:.14em;text-transform:uppercase;opacity:.55}
  .val{font-family:"Geist Mono",ui-monospace,monospace;font-size:12px;margin-top:4px}
  .parties{display:grid;grid-template-columns:1fr 1fr;gap:48px;margin-bottom:20px}
  .parties h3{margin:0 0 6px;font-size:9.5px;letter-spacing:.14em;text-transform:uppercase;
    opacity:.55;font-weight:500}
  .parties .name{font-family:"Instrument Serif",Georgia,serif;font-size:17px;line-height:1.2}
  .parties .soft{opacity:.7;margin-top:4px}
  .parties .ids{font-family:"Geist Mono",ui-monospace,monospace;font-size:10px;opacity:.55;margin-top:6px}
  table.items{width:100%;border-collapse:collapse;margin-bottom:8px}
  table.items th{text-align:left;font-size:9.5px;letter-spacing:.14em;text-transform:uppercase;
    opacity:.55;font-weight:500;padding:8px 4px;border-bottom:1px solid ${esc(d.style.contentText)}}
  table.items th.num,table.items td.num{text-align:right;
    font-family:"Geist Mono",ui-monospace,monospace}
  table.items td{padding:9px 4px;border-bottom:1px solid rgba(0,0,0,.08);vertical-align:top}
  table.items .desc{opacity:.6}
  .totals{display:flex;justify-content:flex-end;margin:12px 0 16px}
  .totals .box{width:360px}
  .totals .row{display:flex;justify-content:space-between;padding:6px 0;opacity:.75}
  .totals .row.b{border-bottom:1px solid rgba(0,0,0,.15)}
  .totals .grand{display:flex;justify-content:space-between;align-items:baseline;
    padding:12px 0;border-bottom:2px solid ${esc(d.style.contentText)};opacity:1}
  .totals .grand .l{font-family:"Instrument Serif",Georgia,serif;font-style:italic;font-size:18px}
  .totals .grand .r{font-family:"Geist Mono",ui-monospace,monospace;font-size:22px;font-weight:500}
  .pay{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}
  .pay .box{border:1px solid ${esc(d.style.contentText)};padding:12px 14px;
    font-family:"Geist Mono",ui-monospace,monospace}
  .pay .box.alt{border-color:rgba(0,0,0,.2)}
  .pay .grid{display:grid;grid-template-columns:auto 1fr;gap:4px 12px;font-size:10.5px;margin-top:6px}
  .pay .grid .k{opacity:.55}
  .ftr{margin-top:auto;background:${esc(d.style.footerBg)};color:${esc(d.style.footerText)};
    padding:18px 60px;display:grid;grid-template-columns:1.4fr 1fr;gap:24px;font-size:9.5px;line-height:1.5}
  .ftr .k{font-size:9.5px;letter-spacing:.14em;text-transform:uppercase;opacity:.6;margin-bottom:4px}
  @media print{body{background:#fff}.a4{margin:0;box-shadow:none}}
</style>
</head>
<body>
<div class="a4">
  <div class="hdr">
    <div>
      <div class="name">${esc(d.sender.name)}</div>
      <div class="tag">${esc(d.sender.tagline || "")}</div>
    </div>
    <div class="title">${esc(title)}</div>
  </div>

  <div class="body">
    <div class="meta">${meta}</div>

    <div class="parties">
      <div>
        <h3>${esc(L.billTo)}</h3>
        <div class="name">${esc(d.client.name)}</div>
        ${d.client.attn ? `<div class="soft">${esc(d.client.attn)}</div>` : ""}
        <div class="soft">${(d.client.address || []).map(esc).join("<br/>")}</div>
        ${d.client.orgnr ? `<div class="ids">${esc(L.orgNumber)} ${esc(d.client.orgnr)}</div>` : ""}
      </div>
      <div>
        <h3>${esc(L.from)}</h3>
        <div>${esc(d.sender.name)} ${esc(d.sender.tagline || "")}</div>
        <div class="soft">${(d.sender.address || []).map(esc).join("<br/>")}</div>
        <div class="ids">${esc(L.orgNumber)} ${esc(d.sender.orgnr)}<br/>${esc(d.sender.momsnr || "")}</div>
      </div>
    </div>

    <table class="items">
      <thead><tr>
        <th style="width:55%">${esc(L.description)}</th>
        <th class="num" style="width:10%">${esc(L.quantity)}</th>
        <th class="num" style="width:17%">${esc(L.unitPrice)}</th>
        <th class="num" style="width:18%">${esc(L.amount)}</th>
      </tr></thead>
      <tbody>${itemsRows}</tbody>
    </table>

    <div class="totals"><div class="box">
      <div class="row b"><span>${esc(L.subtotal)}</span><span>${sym(t.subtotal)}</span></div>
      <div class="row b"><span>${esc(L.vat)} ${Math.round((d.momsRate || 0) * 100)} %</span><span>${sym(t.moms)}</span></div>
      <div class="grand"><span class="l">${esc(L.total)}</span><span class="r">${sym(t.total)}</span></div>
    </div></div>

    <div class="pay">
      <div class="box">
        <div class="lbl">${esc(L.payment)}</div>
        <div class="grid">
          <span class="k">${esc(L.bankgiro)}</span><span>${esc(d.sender.bankgiro || "")}</span>
          <span class="k">${esc(L.ocr)}</span><span><b>${esc(d.meta.ocr || "")}</b></span>
          <span class="k">${esc(L.amount)}</span><span><b>${sym(t.total)}</b></span>
          <span class="k">${esc(L.dueDate)}</span><span>${esc(d.meta.dueShort)}</span>
        </div>
      </div>
      <div class="box alt">
        <div class="lbl">${esc(L.internationalPayment)}</div>
        <div class="grid">
          <span class="k">${esc(L.bank)}</span><span>${esc(d.sender.bank || "")}</span>
          <span class="k">${esc(L.iban)}</span><span>${esc(d.sender.iban || "")}</span>
          <span class="k">${esc(L.bic)}</span><span>${esc(d.sender.bic || "")}</span>
        </div>
      </div>
    </div>
  </div>

  <div class="ftr">
    <div>
      <div class="k">${esc(L.paymentTermsTitle)}</div>
      <div>${esc(d.legal.payment || "")}</div>
    </div>
    <div>
      <div class="k">${esc(L.companyInfo)}</div>
      <div>${esc(d.sender.orgnr)} · ${esc(d.sender.momsnr || "")}</div>
      <div>${esc(d.legal.fskatt || "")}</div>
    </div>
  </div>
</div>
</body>
</html>`;
  }

  return { renderFaktura, computeTotals, DEFAULT_DOC, DEFAULT_LABELS_SV, DEFAULT_LABELS_EN };
});
