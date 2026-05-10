#!/usr/bin/env node
// server.js — One endpoint, JSON in, PDF (or HTML) out.
//
// Usage:
//   POST /pdf   { ...doc }  → application/pdf
//   POST /html  { ...doc }  → text/html
//   GET  /healthz
//
// Env:
//   PORT                       (default 3030)
//   FAKTURA_FONTS_HREF         (default /fonts/fonts.css — self-hosted)
//   PUPPETEER_EXECUTABLE_PATH  (set by Docker image)

const express = require("express");
const path    = require("path");
const fs      = require("fs");
const puppeteer = require("puppeteer");
const { renderFaktura } = require("./renderer.js");

const PORT = process.env.PORT || 3030;
const FONTS_HREF = process.env.FAKTURA_FONTS_HREF || "/fonts/fonts.css";

// Long-lived browser — warm Chromium, fast subsequent renders.
let _browser;
async function getBrowser() {
  if (_browser && _browser.isConnected()) return _browser;
  _browser = await puppeteer.launch({
    headless: "new",
    executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || undefined,
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
  });
  return _browser;
}

async function htmlToPdf(html, opts = {}) {
  const browser = await getBrowser();
  const page = await browser.newPage();
  try {
    // Resolve /fonts/* against the local filesystem so the headless browser
    // can fetch the self-hosted CSS without any HTTP server. Everything else
    // (data: URIs, http(s)) passes through unchanged.
    await page.setRequestInterception(true);
    page.on("request", (req) => {
      const url = req.url();
      const m = url.match(/^https?:\/\/[^/]+(\/fonts\/[^?#]+)/) || url.match(/^file:\/\/.*?(\/fonts\/[^?#]+)/);
      const localPath = m ? m[1] : (url.startsWith("/fonts/") ? url : null);
      if (localPath) {
        const fp = path.join(__dirname, localPath);
        if (fs.existsSync(fp)) {
          const ext = path.extname(fp).slice(1);
          const ct = { css: "text/css", woff2: "font/woff2", woff: "font/woff" }[ext] || "application/octet-stream";
          return req.respond({ status: 200, contentType: ct, body: fs.readFileSync(fp) });
        }
      }
      req.continue();
    });

    await page.setContent(html, { waitUntil: "networkidle0" });
    await page.evaluate(() => document.fonts && document.fonts.ready);
    return await page.pdf({
      format: opts.format || "A4",
      printBackground: true,
      margin: opts.margin || { top: 0, right: 0, bottom: 0, left: 0 },
      ...opts.pdf,
    });
  } finally { await page.close(); }
}

const app = express();
app.use(express.json({ limit: "5mb" }));

// Serve self-hosted fonts (for direct browser use of /html output).
app.use("/fonts", express.static(path.join(__dirname, "fonts"), {
  maxAge: "30d", immutable: true,
}));

app.get("/healthz", (_req, res) => res.json({ ok: true }));

app.post("/html", (req, res) => {
  try {
    const html = renderFaktura(req.body || {}, { fontsHref: FONTS_HREF });
    res.type("html").send(html);
  } catch (e) { res.status(400).json({ error: e.message }); }
});

app.post("/pdf", async (req, res) => {
  try {
    const doc = req.body || {};
    const html = renderFaktura(doc, { fontsHref: FONTS_HREF });
    const filename = `${doc.docType || "faktura"}-${(doc.meta && doc.meta.nr) || "doc"}.pdf`;
    const buf = await htmlToPdf(html, doc.pdfOptions || {});
    res.type("application/pdf")
       .set("Content-Disposition", `inline; filename="${filename.replace(/[^\w.\-]/g, "_")}"`)
       .send(buf);
  } catch (e) {
    console.error(e);
    res.status(500).json({ error: e.message });
  }
});

// Graceful shutdown
async function shutdown() {
  try { if (_browser) await _browser.close(); } catch {}
  process.exit(0);
}
process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);

app.listen(PORT, () => console.log(`Faktura service listening on :${PORT}`));
