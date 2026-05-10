#!/bin/bash
# install.sh — Installerar billing-system v2 på Ubuntu-server.
# Kör som administrator.

set -e

INSTALL_DIR="${HOME}/billing-system"
WORKSPACE_DIR="${HOME}/.openclaw/workspace-fyodor"

echo "🦞 Installerar Billing System v2..."

# 1. Kontrollera Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 saknas. Installera först."
    exit 1
fi

# 2. Installera requests
echo "📦 Installerar Python-beroenden..."
pip install requests --break-system-packages --quiet || pip install requests --quiet

# 3. Skapa filstruktur
echo "📁 Skapar mappar..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/data"
mkdir -p "$HOME/documents/invoices"

# 4. Kopiera från denna paketkatalog till installationsplatsen
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "📂 Kopierar filer från $SCRIPT_DIR till $INSTALL_DIR..."
cp -r "$SCRIPT_DIR/tools"     "$INSTALL_DIR/"
cp -r "$SCRIPT_DIR/templates" "$INSTALL_DIR/"
cp -r "$SCRIPT_DIR/docs"      "$INSTALL_DIR/"
cp    "$SCRIPT_DIR/README.md" "$INSTALL_DIR/"

# 5. Gör alla skript exekverbara
find "$INSTALL_DIR/tools" -name "*.py" -exec chmod +x {} \;

# 6. Kontrollera Faktura Constructor
echo "🔍 Kontrollerar Faktura Constructor på localhost:3030..."
if curl -s --max-time 5 http://localhost:3030/healthz | grep -q '"ok":true'; then
    echo "✅ Faktura Constructor körs"
else
    echo "⚠️  Faktura Constructor svarar inte. Starta den innan du börjar skapa fakturor."
    echo "   Se ~/faktura-service/README.md"
fi

# 7. Uppdatera Fjodors SOUL.md
if [ -d "$WORKSPACE_DIR" ]; then
    echo "🤖 Uppdaterar Fjodors SOUL.md..."
    cp "$SCRIPT_DIR/SOUL_fyodor.md" "$WORKSPACE_DIR/SOUL.md"
    echo "✅ SOUL.md uppdaterad"
else
    echo "⚠️  $WORKSPACE_DIR finns inte. Skapa Fjodor-agenten först eller kopiera SOUL_fyodor.md manuellt."
fi

# 8. Initialisera tomma databaser
for db in senders recipients invoices phone_map; do
    target="$INSTALL_DIR/data/${db}.json"
    if [ ! -f "$target" ]; then
        echo '{"version": 2, "uppdaterad": null}' > "$target"
        echo "📄 Skapat tom $target"
    fi
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Installation klar!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Nästa steg:"
echo "  1. Lägg till din första avsändare:"
echo "     python3 $INSTALL_DIR/tools/db/db_senders.py --lagg-till '{...}'"
echo ""
echo "  2. Koppla telefonnummer till avsändaren:"
echo "     python3 $INSTALL_DIR/tools/db/db_phone_map.py --koppla \"+46...\" \"559...\""
echo ""
echo "  3. Starta om OpenClaw gateway:"
echo "     openclaw gateway restart"
echo ""
echo "Se README.md för fullständig dokumentation."
