#!/usr/bin/env node
// render.js — CLI wrapper around renderer.js
//
// Usage:
//   node render.js doc.json > invoice.html
//   cat doc.json | node render.js > invoice.html
//   node render.js doc.json invoice.html

const fs = require("fs");
const { renderFaktura } = require("./renderer.js");

function readInput() {
  const arg = process.argv[2];
  if (arg && arg !== "-") return fs.readFileSync(arg, "utf8");
  return fs.readFileSync(0, "utf8"); // stdin
}

try {
  const json = JSON.parse(readInput());
  const html = renderFaktura(json);
  const out = process.argv[3];
  if (out) {
    fs.writeFileSync(out, html);
    console.error(`Wrote ${out} (${html.length} bytes)`);
  } else {
    process.stdout.write(html);
  }
} catch (e) {
  console.error("Error:", e.message);
  process.exit(1);
}
