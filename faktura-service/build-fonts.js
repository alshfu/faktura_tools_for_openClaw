#!/usr/bin/env node
// build-fonts.js — Generate self-hosted fonts.css from @fontsource packages.
//
// Reads font files from node_modules/@fontsource/*/files and copies them
// (+ a single combined fonts.css) into ./fonts/. Run automatically via
// `postinstall`; can also be invoked manually with `npm run build:fonts`.
//
// Falls back silently if @fontsource packages aren't installed (so a pure
// HTML-only install still works without the optional font deps).

const fs = require("fs");
const path = require("path");

const FONTS = [
  // family,           pkg,                          weights,      styles
  ["Geist",            "@fontsource/geist",          [300,400,500,600], ["normal"]],
  ["Geist Mono",       "@fontsource/geist-mono",     [400,500],         ["normal"]],
  ["Inter",            "@fontsource/inter",          [300,400,500,600], ["normal"]],
  ["Instrument Serif", "@fontsource/instrument-serif",[400],            ["normal","italic"]],
  ["Fraunces",         "@fontsource/fraunces",       [400,500,600],     ["normal","italic"]],
  ["JetBrains Mono",   "@fontsource/jetbrains-mono", [400,500],         ["normal"]],
];

const OUT_DIR = path.join(__dirname, "fonts");
const FILES_DIR = path.join(OUT_DIR, "files");

function ensureDir(p) { fs.mkdirSync(p, { recursive: true }); }

function tryPickFile(pkgDir, family, weight, style) {
  // Fontsource v5 layout: <pkg>/files/<slug>-latin-<weight>-<style>.woff2
  const slug = family.toLowerCase().replace(/\s+/g, "-");
  const candidates = [
    `${slug}-latin-${weight}-${style}.woff2`,
    `${slug}-latin-ext-${weight}-${style}.woff2`,
  ];
  for (const c of candidates) {
    const p = path.join(pkgDir, "files", c);
    if (fs.existsSync(p)) return { src: p, name: c };
  }
  return null;
}

function build() {
  ensureDir(OUT_DIR);
  ensureDir(FILES_DIR);

  const blocks = [];
  let copied = 0;

  for (const [family, pkg, weights, styles] of FONTS) {
    let pkgDir;
    try { pkgDir = path.dirname(require.resolve(`${pkg}/package.json`)); }
    catch { console.warn(`[build-fonts] skipping ${pkg} (not installed)`); continue; }

    for (const style of styles) {
      for (const w of weights) {
        const found = tryPickFile(pkgDir, family, w, style);
        if (!found) continue;
        const dest = path.join(FILES_DIR, found.name);
        fs.copyFileSync(found.src, dest);
        copied++;
        blocks.push(
          `@font-face{font-family:"${family}";font-style:${style};font-weight:${w};` +
          `font-display:swap;src:url("./files/${found.name}") format("woff2")}`
        );
      }
    }
  }

  const css = blocks.join("\n") + "\n";
  fs.writeFileSync(path.join(OUT_DIR, "fonts.css"), css);
  console.log(`[build-fonts] wrote fonts/fonts.css with ${blocks.length} faces ` +
              `(${copied} font files copied)`);
}

try { build(); }
catch (e) { console.warn("[build-fonts] failed:", e.message); }
