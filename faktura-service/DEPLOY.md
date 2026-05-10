# Deploy — JSON in, PDF out

One container. One endpoint. Send JSON → receive PDF.

## Build & run

```bash
# 1) Clone / copy these files to the VPS
git clone <your-repo> faktura && cd faktura

# 2) Build the image
docker compose build

# 3) Start
docker compose up -d

# 4) Verify
curl http://localhost:3030/healthz
# → {"ok":true}
```

That's it. Chromium + fonts + Node are all baked in.

## Generate a PDF

```bash
curl -X POST http://localhost:3030/pdf \
  -H "Content-Type: application/json" \
  -d @examples/doc.json \
  -o invoice.pdf
```

Open `invoice.pdf` — done.

## From your agent (Node)

```js
const res = await fetch("http://localhost:3030/pdf", {
  method:  "POST",
  headers: { "Content-Type": "application/json" },
  body:    JSON.stringify(doc),  // your faktura JSON
});
const pdfBuffer = Buffer.from(await res.arrayBuffer());
fs.writeFileSync("invoice.pdf", pdfBuffer);
```

## From your agent (Python)

```python
import requests
r = requests.post("http://localhost:3030/pdf", json=doc)
open("invoice.pdf", "wb").write(r.content)
```

## Endpoints

| Method | Path        | Body                | Returns           |
|--------|-------------|---------------------|-------------------|
| POST   | `/pdf`      | faktura JSON        | `application/pdf` |
| POST   | `/html`     | faktura JSON        | `text/html`       |
| GET    | `/healthz`  | —                   | `{ok:true}`       |

Optional per-request override:

```jsonc
{
  "docType": "kvitto",
  "sender":  { "...": "..." },
  "items":   [ ],
  "pdfOptions": {
    "format": "A4",
    "margin": { "top": "10mm", "bottom": "10mm" }
  }
}
```

## Without Docker (bare VPS)

```bash
sudo apt install -y nodejs npm chromium
npm install                 # builds fonts/fonts.css via postinstall
PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium node server.js
```

## Self-hosted fonts

`build-fonts.js` runs on `npm install` and bakes Geist / Inter / Instrument Serif / Fraunces / Geist Mono / JetBrains Mono from `@fontsource/*` into `fonts/`. The server serves them at `/fonts/fonts.css`. **No outbound Google Fonts needed.**

To use Google Fonts CDN instead (smaller image), set:

```
FAKTURA_FONTS_HREF=https://fonts.googleapis.com/css2?family=Geist...
```

## File inventory (server)

```
faktura/
├── Dockerfile
├── docker-compose.yml
├── package.json
├── renderer.js          # JSON → HTML
├── render.js            # CLI: JSON → HTML file
├── render-pdf.js        # CLI / lib: JSON → PDF file
├── server.js            # HTTP service
├── build-fonts.js       # Bake @fontsource → fonts/fonts.css
├── fonts/               # Generated at install time
├── examples/doc.json
├── SCHEMA.md            # JSON key reference
├── API.md               # In-browser FakturaAPI (editor only)
└── README.md            # Long-form docs
```

## Updating

```bash
git pull
docker compose up -d --build
```
