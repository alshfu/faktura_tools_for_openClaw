# Faktura service — JSON → PDF in one HTTP call
# Multi-stage build keeps the final image small and reproducible.

FROM node:20-bookworm-slim AS deps
WORKDIR /app

# Install Chromium + minimal deps for Puppeteer headless rendering.
RUN apt-get update && apt-get install -y --no-install-recommends \
      chromium \
      fonts-liberation ca-certificates \
      libasound2 libatk-bridge2.0-0 libatk1.0-0 libcairo2 libcups2 \
      libdbus-1-3 libexpat1 libfontconfig1 libgbm1 libglib2.0-0 \
      libnspr4 libnss3 libpango-1.0-0 libpangocairo-1.0-0 \
      libx11-6 libx11-xcb1 libxcb1 libxcomposite1 libxcursor1 \
      libxdamage1 libxext6 libxfixes3 libxi6 libxrandr2 libxrender1 \
      libxss1 libxtst6 \
   && rm -rf /var/lib/apt/lists/*

# Use system Chromium, skip Puppeteer's bundled download.
ENV PUPPETEER_SKIP_DOWNLOAD=true
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium

# Install Node deps (incl. @fontsource/* — postinstall builds fonts/fonts.css).
COPY package.json ./
RUN npm install --omit=dev

# Copy source.
COPY renderer.js render.js render-pdf.js server.js build-fonts.js ./
COPY examples ./examples

# Re-run font bake explicitly (in case postinstall was skipped earlier).
RUN node build-fonts.js

# Non-root user for Chromium (avoids --no-sandbox warnings in logs).
RUN useradd --system --create-home --shell /bin/bash faktura \
 && chown -R faktura:faktura /app
USER faktura

ENV PORT=3030
ENV FAKTURA_FONTS_HREF=/fonts/fonts.css
EXPOSE 3030

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD wget -qO- http://127.0.0.1:3030/healthz || exit 1

CMD ["node", "server.js"]
