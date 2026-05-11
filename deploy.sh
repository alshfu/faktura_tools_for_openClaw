#!/bin/bash
#
# deploy.sh — Master deployment-script för Billing System v2.
#
# Tre lägen:
#   ./deploy.sh install   — Full installation från grunden
#   ./deploy.sh update    — Uppdatera från GitHub (behåller data och konfiguration)
#   ./deploy.sh status    — Kontrollera status på alla komponenter
#
# Hanterar:
#   1. Python-beroenden
#   2. Faktura Constructor via Docker (eller PM2 om Docker saknas)
#   3. OpenClaw-agenten Fjodor (skapa ny eller uppdatera befintlig)
#   4. Initiering av tomma databaser
#   5. Workspace-konfiguration (SOUL.md, USER.md)
#
# Användning:
#   curl -fsSL https://raw.githubusercontent.com/alshfu/faktura_tools_for_openClaw/main/deploy.sh | bash -s install
#   eller
#   cd ~/billing-system && ./deploy.sh install
#
set -e

# ── Konfiguration ─────────────────────────────────────────────────────────────

GITHUB_REPO="https://github.com/alshfu/faktura_tools_for_openClaw.git"
GITHUB_BRANCH="main"

INSTALL_DIR="${BILLING_INSTALL_DIR:-$HOME/billing-system}"
FAKTURA_DIR="$INSTALL_DIR/faktura-service"
WORKSPACE_DIR="$HOME/.openclaw/workspace-fyodor"
INVOICES_DIR="$HOME/documents/invoices"

AGENT_NAME="${AGENT_NAME:-fyodor}"
AGENT_MODEL="${AGENT_MODEL:-moonshot/kimi-k2.6}"

FAKTURA_PORT="${FAKTURA_PORT:-3030}"
FAKTURA_SERVICE_URL="http://localhost:$FAKTURA_PORT"

# ── Färger ────────────────────────────────────────────────────────────────────

if [ -t 1 ]; then
    BLUE='\033[0;34m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
    RED='\033[0;31m';  RESET='\033[0m';    BOLD='\033[1m'
else
    BLUE=''; GREEN=''; YELLOW=''; RED=''; RESET=''; BOLD=''
fi

info()    { echo -e "${BLUE}ℹ${RESET}  $1"; }
ok()      { echo -e "${GREEN}✅${RESET} $1"; }
warn()    { echo -e "${YELLOW}⚠️${RESET}  $1"; }
err()     { echo -e "${RED}❌${RESET} $1" >&2; }
header()  { echo -e "\n${BOLD}━━━ $1 ━━━${RESET}"; }

# ── Hjälpfunktioner ───────────────────────────────────────────────────────────

cmd_exists() { command -v "$1" >/dev/null 2>&1; }

ensure_dir() {
    [ -d "$1" ] || mkdir -p "$1"
}

backup_file() {
    [ -f "$1" ] && cp "$1" "$1.bak.$(date +%Y%m%d_%H%M%S)" && info "Säkerhetskopia: $1.bak.*"
}

# ── Steg ──────────────────────────────────────────────────────────────────────

check_prerequisites() {
    header "Kontrollerar förutsättningar"

    if ! cmd_exists python3; then
        err "Python 3 saknas. Installera med: sudo apt install python3 python3-pip"
        exit 1
    fi
    ok "Python 3: $(python3 --version)"

    if ! cmd_exists openclaw; then
        err "OpenClaw saknas. Installera först (se https://openclaw.ai/install)"
        exit 1
    fi
    ok "OpenClaw: $(openclaw --version 2>&1 | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo 'okänd version')"

    if ! cmd_exists curl; then
        err "curl saknas. Installera med: sudo apt install curl"
        exit 1
    fi

    if ! cmd_exists git; then
        warn "git saknas — uppdateringar från GitHub kommer inte fungera"
        warn "Installera med: sudo apt install git"
    else
        ok "git: $(git --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')"
    fi

    # Docker eller PM2 för Faktura Service
    if cmd_exists docker && docker info >/dev/null 2>&1; then
        ok "Docker tillgängligt"
        FAKTURA_RUNTIME="docker"
    elif cmd_exists node; then
        ok "Node.js: $(node --version) (fallback utan Docker)"
        FAKTURA_RUNTIME="node"
        if ! cmd_exists pm2; then
            warn "PM2 saknas — installerar..."
            npm install -g pm2 2>/dev/null || sudo npm install -g pm2
        fi
    else
        err "Varken Docker eller Node.js är installerat. Faktura Constructor kan inte köras."
        err "Installera Docker: https://docs.docker.com/engine/install/ubuntu/"
        exit 1
    fi
}

install_python_deps() {
    header "Installerar Python-beroenden"

    local pkgs="requests"
    if pip install $pkgs --break-system-packages --quiet 2>/dev/null; then
        ok "Python-paket installerade (system)"
    elif pip install $pkgs --quiet 2>/dev/null; then
        ok "Python-paket installerade"
    elif pip3 install $pkgs --quiet 2>/dev/null; then
        ok "Python-paket installerade (pip3)"
    else
        warn "pip misslyckades — försök installera manuellt: pip install $pkgs"
    fi
}

clone_or_update_repo() {
    header "Hämtar källkod"

    if [ -d "$INSTALL_DIR/.git" ]; then
        info "Befintlig installation hittades — uppdaterar..."
        cd "$INSTALL_DIR"
        git fetch --quiet
        local current_branch
        current_branch=$(git rev-parse --abbrev-ref HEAD)
        if [ "$current_branch" != "$GITHUB_BRANCH" ]; then
            warn "Befinner sig på branch '$current_branch', byter till '$GITHUB_BRANCH'"
            git checkout "$GITHUB_BRANCH" --quiet
        fi
        # Stash any local changes so pull can proceed cleanly
        local stashed=0
        if ! git diff --quiet || ! git diff --cached --quiet; then
            git stash --quiet
            stashed=1
        fi
        git pull --quiet
        if [ "$stashed" = "1" ]; then
            git stash pop --quiet 2>/dev/null || warn "Kunde inte återställa lokala ändringar (git stash pop misslyckades)"
        fi
        ok "Uppdaterat från GitHub ($(git rev-parse --short HEAD))"
    elif [ -d "$INSTALL_DIR" ] && [ "$(ls -A "$INSTALL_DIR" 2>/dev/null)" ]; then
        warn "$INSTALL_DIR finns men är inte git-repo. Hoppar över git-hämtning."
        warn "Om du vill ha automatiska uppdateringar — säkerhetskopiera, ta bort mappen och kör install igen."
    elif cmd_exists git; then
        info "Klonar repo från GitHub..."
        ensure_dir "$(dirname "$INSTALL_DIR")"
        git clone --branch "$GITHUB_BRANCH" --depth 1 "$GITHUB_REPO" "$INSTALL_DIR" --quiet
        ok "Klonat till $INSTALL_DIR"
    else
        warn "git saknas — installation måste göras manuellt (kopiera filerna till $INSTALL_DIR)"
    fi
}

setup_faktura_service() {
    header "Konfigurerar Faktura Constructor"

    if [ ! -d "$FAKTURA_DIR" ]; then
        err "$FAKTURA_DIR saknas. Hämta från repo eller installera manuellt."
        return 1
    fi

    # Kontrollera om redan kör
    if curl -s --max-time 3 "$FAKTURA_SERVICE_URL/healthz" 2>/dev/null | grep -q '"ok":true'; then
        ok "Faktura Constructor körs redan på $FAKTURA_SERVICE_URL"
        return 0
    fi

    if [ "$FAKTURA_RUNTIME" = "docker" ]; then
        cd "$FAKTURA_DIR"
        info "Bygger Docker-image (detta tar 1-2 minuter första gången)..."
        if docker compose build --quiet 2>/dev/null; then
            ok "Docker-image byggd"
        else
            docker-compose build --quiet 2>/dev/null || {
                err "Docker build misslyckades"
                return 1
            }
        fi

        info "Startar Faktura Constructor..."
        docker compose up -d 2>/dev/null || docker-compose up -d

        sleep 3

    elif [ "$FAKTURA_RUNTIME" = "node" ]; then
        cd "$FAKTURA_DIR"
        info "Installerar npm-paket (detta tar 1-2 minuter)..."
        npm install --silent --no-fund --no-audit 2>&1 | tail -5

        # Hitta Chromium
        local chromium_path
        chromium_path=$(which chromium 2>/dev/null || which chromium-browser 2>/dev/null || echo "")
        if [ -z "$chromium_path" ]; then
            warn "Chromium hittas inte. Installera: sudo apt install chromium"
            warn "Försöker köra med Puppeteers inbyggda Chromium ändå..."
        fi

        info "Startar via PM2..."
        PUPPETEER_EXECUTABLE_PATH="$chromium_path" pm2 start server.js --name faktura --silent 2>/dev/null || \
            pm2 restart faktura --silent
        pm2 save --silent
    fi

    # Verifiera
    sleep 2
    local attempts=0
    while [ $attempts -lt 10 ]; do
        if curl -s --max-time 3 "$FAKTURA_SERVICE_URL/healthz" 2>/dev/null | grep -q '"ok":true'; then
            ok "Faktura Constructor svarar på $FAKTURA_SERVICE_URL"
            return 0
        fi
        sleep 1
        attempts=$((attempts + 1))
    done

    warn "Faktura Constructor verkar inte svara. Kolla loggarna:"
    if [ "$FAKTURA_RUNTIME" = "docker" ]; then
        echo "    docker compose -f $FAKTURA_DIR/docker-compose.yml logs --tail 50"
    else
        echo "    pm2 logs faktura"
    fi
    return 1
}

create_or_update_agent() {
    header "Konfigurerar OpenClaw-agenten '$AGENT_NAME'"

    # Kontrollera om agenten redan finns
    if openclaw agents list 2>/dev/null | grep -q "^- $AGENT_NAME"; then
        info "Agent '$AGENT_NAME' finns redan — uppdaterar workspace"
        AGENT_EXISTS=1
    else
        info "Skapar ny agent '$AGENT_NAME'..."
        AGENT_EXISTS=0

        # Försök non-interactive först (om versionen stödjer det)
        if openclaw agents add "$AGENT_NAME" \
              --workspace "$WORKSPACE_DIR" \
              --model "$AGENT_MODEL" \
              --bind whatsapp \
              --non-interactive 2>/dev/null; then
            ok "Agent skapad (non-interactive)"
        else
            warn "Auto-mode misslyckades — kör manuellt:"
            echo ""
            echo "    openclaw agents add $AGENT_NAME \\"
            echo "      --workspace $WORKSPACE_DIR \\"
            echo "      --model $AGENT_MODEL \\"
            echo "      --bind whatsapp"
            echo ""
            warn "När agenten är skapad, kör 'deploy.sh install' igen för att färdigställa konfigurationen."
            return 0
        fi
    fi

    # Uppdatera SOUL.md och USER.md
    ensure_dir "$WORKSPACE_DIR"

    if [ -f "$INSTALL_DIR/SOUL_fyodor.md" ]; then
        backup_file "$WORKSPACE_DIR/SOUL.md"
        cp "$INSTALL_DIR/SOUL_fyodor.md" "$WORKSPACE_DIR/SOUL.md"
        ok "SOUL.md uppdaterad"
    fi

    if [ -f "$INSTALL_DIR/USER_fyodor.md" ]; then
        cp "$INSTALL_DIR/USER_fyodor.md" "$WORKSPACE_DIR/USER.md"
        ok "USER.md uppdaterad"
    fi

    # Rensa gamla sessions för att tvinga ny start med uppdaterat SOUL.md
    local sessions_dir="$HOME/.openclaw/agents/$AGENT_NAME/sessions"
    if [ -d "$sessions_dir" ]; then
        rm -f "$sessions_dir"/*.jsonl 2>/dev/null || true
        info "Gamla sessions rensade — agenten startar fräscht"
    fi
}

init_databases() {
    header "Initierar databaser"

    ensure_dir "$INSTALL_DIR/data"
    ensure_dir "$INVOICES_DIR"

    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    declare -A db_init=(
        ["senders"]='{"version": 2, "uppdaterad": "'"$timestamp"'", "avsandare": {}}'
        ["recipients"]='{"version": 2, "uppdaterad": "'"$timestamp"'", "mottagare": {}}'
        ["invoices"]='{"version": 2, "uppdaterad": "'"$timestamp"'", "fakturor": {}}'
        ["phone_map"]='{"version": 2, "uppdaterad": "'"$timestamp"'", "kopplingar": {}}'
        ["counters"]='{"version": 2, "fakturanummer": {}}'
    )

    for db in "${!db_init[@]}"; do
        local target="$INSTALL_DIR/data/${db}.json"
        if [ ! -f "$target" ]; then
            echo "${db_init[$db]}" > "$target"
            ok "Skapat: $target"
        else
            info "Finns redan: $target (orörd)"
        fi
    done
}

make_scripts_executable() {
    header "Gör skript exekverbara"
    find "$INSTALL_DIR/tools" -name "*.py" -exec chmod +x {} \; 2>/dev/null
    chmod +x "$INSTALL_DIR"/*.sh 2>/dev/null || true
    ok "Behörigheter satta"
}

restart_gateway() {
    header "Startar om OpenClaw gateway"
    if openclaw gateway restart 2>&1 | head -3; then
        ok "Gateway omstartad"
    else
        warn "Kunde inte starta om gateway — gör det manuellt: openclaw gateway restart"
    fi
}

show_status() {
    header "Systemstatus"

    # Faktura Constructor
    if curl -s --max-time 3 "$FAKTURA_SERVICE_URL/healthz" 2>/dev/null | grep -q '"ok":true'; then
        ok "Faktura Constructor: kör på $FAKTURA_SERVICE_URL"
    else
        err "Faktura Constructor: svarar inte"
    fi

    # OpenClaw agent
    if openclaw agents list 2>/dev/null | grep -q "^- $AGENT_NAME"; then
        ok "Agent '$AGENT_NAME': registrerad"
    else
        err "Agent '$AGENT_NAME': INTE registrerad"
    fi

    # Workspace-filer
    if [ -f "$WORKSPACE_DIR/SOUL.md" ]; then
        ok "SOUL.md: finns ($(stat -c%s "$WORKSPACE_DIR/SOUL.md" 2>/dev/null || stat -f%z "$WORKSPACE_DIR/SOUL.md") bytes)"
    else
        err "SOUL.md: SAKNAS i $WORKSPACE_DIR"
    fi

    # Databaser
    local db_dir="$INSTALL_DIR/data"
    if [ -d "$db_dir" ]; then
        for db in senders recipients invoices phone_map; do
            if [ -f "$db_dir/$db.json" ]; then
                local count
                count=$(python3 -c "
import json
d = json.load(open('$db_dir/$db.json'))
for k in ('avsandare','mottagare','fakturor','kopplingar'):
    if k in d:
        print(len(d[k])); break
else:
    print(0)
" 2>/dev/null)
                ok "DB $db: $count poster"
            else
                err "DB $db.json: saknas"
            fi
        done
    fi

    # Git-status
    if [ -d "$INSTALL_DIR/.git" ]; then
        cd "$INSTALL_DIR"
        ok "Git: $(git rev-parse --short HEAD) ($(git log -1 --format=%cr))"
    fi

    echo ""
}

# ── Huvudkommandon ────────────────────────────────────────────────────────────

setup_secrets_if_missing() {
    header "Konfiguration av hemligheter"

    local cfg_file="$HOME/.billing-system/config.json"
    local setup_script="$INSTALL_DIR/tools/config/setup_secrets.py"

    if [ ! -f "$setup_script" ]; then
        warn "setup_secrets.py saknas — hoppar"
        return 0
    fi

    if [ -f "$cfg_file" ]; then
        # Kontrollera om allt är ifyllt
        local missing
        missing=$(python3 "$INSTALL_DIR/tools/utils/config.py" --check 2>/dev/null \
                  | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d.get('saknas',[])))" \
                  2>/dev/null || echo "?")
        if [ "$missing" = "0" ]; then
            ok "Konfiguration finns och är komplett"
            return 0
        fi
        warn "Konfiguration finns men saknar $missing fält"
    else
        warn "Ingen konfiguration finns ännu"
    fi

    if [ ! -t 0 ]; then
        # Non-interactive (t.ex. piped curl) — kan inte köra setup
        warn "Ej interaktivt läge — kör manuellt efter installation:"
        echo "    python3 $setup_script"
        return 0
    fi

    if [ "${AUTO_SETUP_SECRETS:-1}" = "1" ]; then
        info "Startar konfigurationsguide..."
        python3 "$setup_script" || warn "Konfigurationsguide avbruten"
    else
        info "AUTO_SETUP_SECRETS=0 — hoppar interaktiv guide"
        echo "    Kör manuellt: python3 $setup_script"
    fi
}

run_test_suite() {
    local mode="$1"   # install | update
    header "Kör testsvit"

    if [ ! -f "$INSTALL_DIR/test_suite.py" ]; then
        warn "test_suite.py saknas — hoppar tester"
        return 0
    fi

    if [ "${SKIP_TESTS:-0}" = "1" ]; then
        info "SKIP_TESTS=1 — hoppar tester"
        return 0
    fi

    # Vänta på att Faktura Constructor är redo
    local attempts=0
    while [ $attempts -lt 15 ]; do
        if curl -s --max-time 2 "$FAKTURA_SERVICE_URL/healthz" 2>/dev/null | grep -q '"ok":true'; then
            break
        fi
        sleep 1
        attempts=$((attempts + 1))
    done

    local test_flags="--no-cleanup"   # behåll data — städas i T10 internt

    info "Startar testsvit (detta tar ~30-60 sekunder)..."
    if python3 "$INSTALL_DIR/test_suite.py" $test_flags; then
        ok "Testsvit: GODKÄND"
    else
        warn "Testsvit: NÅGRA FEL — se utdata ovan"
        warn "Kör manuellt för detaljer: python3 $INSTALL_DIR/test_suite.py --no-cleanup"
    fi
}

cmd_install() {
    echo -e "${BOLD}╔═══════════════════════════════════════╗${RESET}"
    echo -e "${BOLD}║  Billing System v2 — Installation   ║${RESET}"
    echo -e "${BOLD}╚═══════════════════════════════════════╝${RESET}"

    check_prerequisites
    clone_or_update_repo
    install_python_deps
    init_databases
    make_scripts_executable
    setup_faktura_service
    create_or_update_agent
    setup_secrets_if_missing
    restart_gateway
    run_test_suite install

    echo ""
    header "Klart!"
    echo ""
    echo "Nästa steg:"
    echo "  1. Lägg till din första avsändare:"
    echo "     python3 $INSTALL_DIR/tools/db/db_senders.py --lagg-till '{\"org_nummer\":\"...\",...}'"
    echo ""
    echo "  2. Koppla telefonnummer:"
    echo "     python3 $INSTALL_DIR/tools/db/db_phone_map.py --koppla \"+46...\" \"559...\" '{...}'"
    echo ""
    echo "  3. Skriv till agenten på WhatsApp."
    echo ""
    echo "Status:  $0 status"
    echo "Update:  $0 update"
    echo "Tester:  python3 $INSTALL_DIR/test_suite.py"
    echo ""
}

cmd_update() {
    echo -e "${BOLD}╔═══════════════════════════════════════╗${RESET}"
    echo -e "${BOLD}║  Billing System v2 — Uppdatering    ║${RESET}"
    echo -e "${BOLD}╚═══════════════════════════════════════╝${RESET}"

    check_prerequisites
    clone_or_update_repo
    install_python_deps
    make_scripts_executable

    # Uppdatera workspace-filer (utan att röra data)
    create_or_update_agent

    # Starta om Faktura Service om Docker-imagen ändrats
    if [ -d "$FAKTURA_DIR" ] && [ "$FAKTURA_RUNTIME" = "docker" ]; then
        info "Bygger om Faktura Constructor Docker-image..."
        cd "$FAKTURA_DIR"
        docker compose up -d --build --quiet 2>/dev/null || docker-compose up -d --build
    elif [ "$FAKTURA_RUNTIME" = "node" ] && [ -d "$FAKTURA_DIR" ]; then
        cd "$FAKTURA_DIR"
        npm install --silent --no-fund --no-audit 2>&1 | tail -3
        pm2 restart faktura --silent || true
    fi

    restart_gateway
    run_test_suite update
    show_status

    ok "Uppdatering klar"
}

cmd_status() {
    show_status
}

cmd_usage() {
    cat <<USAGE
Användning: $0 <kommando>

Kommandon:
  install    Full installation från grunden (Faktura Constructor + agent + databaser)
  update     Uppdatera från GitHub (behåller data och konfiguration)
  status     Visa status på alla komponenter

Miljövariabler:
  AGENT_NAME           Namn på OpenClaw-agenten (standard: fyodor)
  AGENT_MODEL          LLM-modell (standard: moonshot/kimi-k2.6)
  FAKTURA_PORT         Port för Faktura Constructor (standard: 3030)
  BILLING_INSTALL_DIR  Installationskatalog (standard: \$HOME/billing-system)
  SKIP_TESTS           Sätt till 1 för att hoppa testsviten (standard: 0)
  AUTO_SETUP_SECRETS   Sätt till 0 för att hoppa interaktiv hemlighets-guide (standard: 1)

Exempel:
  $0 install
  $0 update
  AGENT_NAME=fakturabot $0 install

USAGE
}

# ── Main ──────────────────────────────────────────────────────────────────────

case "${1:-}" in
    install)  cmd_install ;;
    update)   cmd_update  ;;
    status)   cmd_status  ;;
    -h|--help|help) cmd_usage ;;
    *)        cmd_usage; exit 1 ;;
esac
