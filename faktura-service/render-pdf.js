#!/usr/bin/env node
// render-pdf.js — Puppeteer wrapper around renderer.js
//
// Generates a print-ready PDF from a document JSON. Uses Chromium's print
// engine via Puppeteer — output is identical to "Save as PDF" from Chrome.
//
// Install:
//   npm i puppeteer
//
// Usage:
//   node render-pdf.js doc.json invoice.pdf
//   cat doc.json | node render-pdf.js - invoice.pdf
//
// Programmatic:
//   const { renderPdf } = require("./render-pdf.js");
//   await renderPdf(doc, "invoice.pdf");
//   const buf = await renderPdf(doc); // returns Buffer if no path given

const fs = require("fs");
const path = require("path");
const { renderFaktura } = require("./renderer.js");

async function renderPdf(doc, outPath, opts = {}) {
  // Lazy-load so the module is usable without puppeteer installed (HTML-only).
  let puppeteer;
  try { puppeteer = require("puppeteer"); }
  catch (e) {
    throw new Error('puppeteer not installed. Run: npm i puppeteer');
  }

  const html = renderFaktura(doc, { fontsHref: opts.fontsHref });
  const browser = await puppeteer.launch({
    headless: "new",
    executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || undefined,
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  });
  try {
    const page = await browser.newPage();
    await page.setContent(html, { waitUntil: "networkidle0" });
    // Make sure web-fonts (Google Fonts) actually finish loading before snapshot.
    await page.evaluate(() => document.fonts && document.fonts.ready);

    const pdfOpts = {
      format: opts.format || "A4",
      printBackground: true,        // keep header/footer color bands
      preferCSSPageSize: false,
      margin: opts.margin || { top: "0mm", right: "0mm", bottom: "0mm", left: "0mm" },
      ...opts.pdf,
    };
    if (outPath) pdfOpts.path = outPath;

    const buf = await page.pdf(pdfOpts);
    return outPath ? outPath : buf;
  } finally {
    await browser.close();
  }
}

// CLI
if (require.main === module) {
  (async () => {
    const inArg = process.argv[2];
    const outArg = process.argv[3] || "invoice.pdf";
    if (!inArg) {
      console.error("Usage: node render-pdf.js <doc.json|-> <out.pdf>");
      process.exit(1);
    }
    const raw = inArg === "-" ? fs.readFileSync(0, "utf8")
                              : fs.readFileSync(inArg, "utf8");
    const doc = JSON.parse(raw);
    await renderPdf(doc, path.resolve(outArg));
    console.error(`Wrote ${outArg}`);
  })().catch((e) => { console.error("Error:", e.message); process.exit(1); });
}

module.exports = { renderPdf };
