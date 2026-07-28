#!/usr/bin/env bash
set -e

# ═══════════════════════════════════════════════════════════════
# Legis Agent — Quick Start Script
# ═══════════════════════════════════════════════════════════════
# Detects missing dependencies, installs them, prompts for API
# keys if unconfigured, and launches the GUI or backend.
# ═══════════════════════════════════════════════════════════════

# ── Colors ───────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ── Detect project root ──────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Helper functions ─────────────────────────────────────────
info()  { printf "${BLUE}ℹ${NC}  %s\n" "$1"; }
ok()    { printf "${GREEN}✓${NC}  %s\n" "$1"; }
warn()  { printf "${YELLOW}⚠${NC}  %s\n" "$1"; }
fail()  { printf "${RED}✗${NC}  %s\n" "$1"; exit 1; }
title() { printf "\n${BOLD}${CYAN}══ %s ══${NC}\n" "$1"; }
ask()   { printf "${CYAN}?${NC}  %s: " "$1"; }

# ── Banner ───────────────────────────────────────────────────
clear
cat << "EOF"
    ╔══════════════════════════════════════════╗
    ║        ⚖️  LEGIS AGENT  🚀              ║
    ║  AI Agents for Legal Documents           ║
    ╚══════════════════════════════════════════╝
EOF
echo ""

# ── Cleanup lingering processes from previous runs ───────────
info "Cleaning up any lingering backend processes..."

# Kill any process on port 8000
PORTS_CLEANED=false
if command -v fuser &>/dev/null; then
    fuser -k 8000/tcp 2>/dev/null && PORTS_CLEANED=true || true
    sleep 1
elif command -v lsof &>/dev/null; then
    PID=$(lsof -ti:8000 2>/dev/null || true)
    if [ -n "$PID" ]; then
        kill -9 $PID 2>/dev/null || true
        PORTS_CLEANED=true
        sleep 1
    fi
elif [ -f /proc/net/tcp ]; then
    # Fallback: parse /proc/net/tcp for port 8000 (hex: 0x1F40)
    INODE=$(awk -F'[: ]+' '$2 ~ /1F40/ {print $10}' /proc/net/tcp 2>/dev/null || true)
    if [ -n "$INODE" ]; then
        PID=$(find /proc -maxdepth 2 -name fd 2>/dev/null | while read d; do
            ls -l "$d" 2>/dev/null | grep -q "socket:\\[$INODE\\]" && echo "$d" | cut -d/ -f3
        done | head -1)
        if [ -n "$PID" ]; then
            kill -9 "$PID" 2>/dev/null || true
            PORTS_CLEANED=true
            sleep 1
        fi
    fi
fi

# Also kill any leftover uvicorn processes by name
pkill -f "uvicorn app.main:app" 2>/dev/null || true
sleep 1

# Kill any stale Tauri backend processes
pkill -f "legis-agent" 2>/dev/null || true
sleep 1

$PORTS_CLEANED && ok "Previous backend stopped" || true

# ═══════════════════════════════════════════════════════════════
# 1. CHECK SYSTEM DEPENDENCIES
# ═══════════════════════════════════════════════════════════════
title "1/6 — Checking system dependencies"

PYTHON_CMD=""
NEEDS_INSTALL=""

# --- Python ---
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
    ok "Python: $(python3 --version)"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
    ok "Python: $(python --version)"
else
    warn "Python not found"
    NEEDS_INSTALL="$NEEDS_INSTALL python3"
fi

# --- Node.js ---
if command -v node &>/dev/null; then
    ok "Node.js: $(node --version)"
else
    warn "Node.js not found"
    NEEDS_INSTALL="$NEEDS_INSTALL nodejs"
fi

# --- npm ---
if command -v npm &>/dev/null; then
    ok "npm: $(npm --version)"
else
    warn "npm not found"
    NEEDS_INSTALL="$NEEDS_INSTALL npm"
fi

# --- Rust / Cargo ---
if command -v cargo &>/dev/null; then
    ok "Cargo: $(cargo --version 2>/dev/null | head -1)"
else
    warn "Rust/Cargo not found (optional — only needed for Tauri desktop GUI)"
fi

# --- Docker (optional) ---
if command -v docker &>/dev/null; then
    ok "Docker: $(docker --version 2>/dev/null | head -1)"
else
    warn "Docker not found (optional — only needed for pgvector)"
fi

# --- Tauri CLI (optional) ---
TAURI_CLI_CMD="cargo tauri"
if cargo tauri --version &>/dev/null; then
    ok "Tauri CLI: $(cargo tauri --version 2>/dev/null | head -1)"
else
    warn "Tauri CLI not found (optional — install with: cargo install tauri-cli --version ^2)"
fi

# ── Install missing dependencies ─────────────────────────────
if [ -n "$NEEDS_INSTALL" ]; then
    title "Installing missing dependencies"
    warn "Missing: $NEEDS_INSTALL"

    if command -v apt &>/dev/null; then
        info "Using apt..."
        sudo apt update
        # shellcheck disable=SC2024
        sudo apt install -y python3 python3-venv python3-pip nodejs npm cargo 2>/dev/null || true
    elif command -v brew &>/dev/null; then
        info "Using brew..."
        brew install python node rust 2>/dev/null || true
    elif command -v pacman &>/dev/null; then
        info "Using pacman..."
        sudo pacman -Sy python nodejs npm rust 2>/dev/null || true
    else
        printf "  ${YELLOW}⚠${NC}  Could not auto-install. Please install manually:\n"
        printf "      - Python 3.12+: https://python.org\n"
        printf "      - Node.js 18+:  https://nodejs.org\n"
        printf "      - Rust:         https://rustup.rs\n"
        echo ""
        ask "Press Enter once you have installed everything"
        read -r _
    fi

    # Re-check after install
    if command -v python3 &>/dev/null; then
        PYTHON_CMD="python3"
        ok "Python now available"
    fi
    if command -v node &>/dev/null; then
        ok "Node.js now available"
    fi
    if command -v cargo &>/dev/null; then
        ok "Cargo now available"
    fi
fi

# ═══════════════════════════════════════════════════════════════
# 2. SET UP PYTHON VIRTUAL ENVIRONMENT
# ═══════════════════════════════════════════════════════════════
title "2/6 — Setting up Python virtual environment"

cd "$SCRIPT_DIR/backend"

if [ ! -d ".venv" ]; then
    info "Creating virtual environment..."
    $PYTHON_CMD -m venv .venv
    ok "Virtual environment created"
else
    ok "Virtual environment exists"
fi

info "Installing backend dependencies..."
.venv/bin/pip install -e ".[dev]" -q 2>/dev/null || .venv/bin/pip install -e ".[dev]"
ok "Backend dependencies installed"

cd "$SCRIPT_DIR"

# ═══════════════════════════════════════════════════════════════
# 3. INSTALL FRONTEND DEPENDENCIES
# ═══════════════════════════════════════════════════════════════
title "3/6 — Installing frontend dependencies"

cd "$SCRIPT_DIR/frontend"

if [ ! -d "node_modules" ]; then
    info "Installing frontend dependencies..."
    npm install
    ok "Frontend dependencies installed"
else
    ok "Frontend dependencies already installed"
fi

cd "$SCRIPT_DIR"

# ═══════════════════════════════════════════════════════════════
# 4. CONFIGURE ENVIRONMENT VARIABLES
# ═══════════════════════════════════════════════════════════════
title "4/6 — Configuring environment variables"

cd "$SCRIPT_DIR/backend"

if [ ! -f ".env" ]; then
    cp .env.example .env
    info ".env file created from .env.example"

    echo ""
    ask "Do you want to configure API keys now? (y/N)"
    read -r CONFIG_KEYS

    if [ "$CONFIG_KEYS" = "y" ] || [ "$CONFIG_KEYS" = "Y" ]; then
        echo ""
        ask "OpenAI API Key (press Enter to skip)"
        read -r OPENAI_KEY
        if [ -n "$OPENAI_KEY" ]; then
            ESCAPED_KEY=$(printf '%s\n' "$OPENAI_KEY" | sed 's/[\/&]/\\&/g')
            sed -i "s/^LITELLM_API_KEY=.*/LITELLM_API_KEY=$ESCAPED_KEY/" .env
            ok "OpenAI API key configured"
        fi

        echo ""
        ask "Anthropic/Claude API Key (press Enter to skip)"
        read -r ANTHROPIC_KEY
        if [ -n "$ANTHROPIC_KEY" ]; then
            echo "ANTHROPIC_API_KEY=$ANTHROPIC_KEY" >> .env
            ok "Anthropic API key configured"
        fi

        echo ""
        info "Tip: Without real API keys the agent runs in simulated mode."
        info "Embeddings, analysis and responses will be mocked."
        info "Get keys at: https://platform.openai.com/api-keys"
    else
        warn "You can configure API keys later by editing backend/.env"
    fi
else
    ok ".env file exists"
fi

cd "$SCRIPT_DIR"

# ═══════════════════════════════════════════════════════════════
# 5. START INFRASTRUCTURE SERVICES (DOCKER / pgvector)
# ═══════════════════════════════════════════════════════════════
title "5/6 — Infrastructure services"

ask "Start pgvector with Docker? (y/N)"
read -r USE_DOCKER

if [ "$USE_DOCKER" = "y" ] || [ "$USE_DOCKER" = "Y" ]; then
    if command -v docker &>/dev/null; then
        info "Starting pgvector..."
        docker compose up -d db
        ok "pgvector running on localhost:5432"
        info "Waiting for PostgreSQL to be ready..."
        sleep 3
    else
        warn "Docker is not installed. Backend will use in-memory store."
    fi
else
    info "Using in-memory vector store (dev mode)"
fi

# ═══════════════════════════════════════════════════════════════
# 6. LAUNCH APPLICATION
# ═══════════════════════════════════════════════════════════════
title "6/6 — Launching Legis Agent"

printf "\n  How would you like to run the app?\n\n"
printf "    ${BOLD}1${NC}  ->  Full Desktop GUI (Tauri + Frontend + Backend)\n"
printf "    ${BOLD}2${NC}  ->  Backend only (API on localhost:8000)\n"
printf "    ${BOLD}3${NC}  ->  Frontend only (React on localhost:1420)\n"
printf "    ${BOLD}4${NC}  ->  Run backend tests\n\n"

ask "Choose an option (1-4)"
read -r RUN_MODE

case $RUN_MODE in
    1)
        printf "\n"
        info "Starting backend in background..."
        cd "$SCRIPT_DIR/backend"
        .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
        BACKEND_PID=$!
        ok "Backend started (PID: $BACKEND_PID)"

        info "Waiting for backend..."
        for _ in $(seq 1 15); do
            if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
                ok "Backend ready"
                break
            fi
            sleep 1
        done

        printf "\n"
        info "===================================="
        info "  Backend API:  http://localhost:8000"
        info "  API Docs:     http://localhost:8000/docs"
        info "  Frontend:     http://localhost:1420"
        info "===================================="
        printf "\n"
        info "Starting Desktop GUI..."
        cd "$SCRIPT_DIR"

        if command -v cargo &>/dev/null && cargo tauri --version &>/dev/null; then
            cargo tauri dev
        else
            warn "Tauri CLI not available. Installing it now..."
            cargo install tauri-cli --version "^2"
            info "Tauri CLI installed. Launching..."
            cargo tauri dev
        fi

        kill $BACKEND_PID 2>/dev/null || true
        ;;

    2)
        printf "\n"
        info "Starting backend on http://localhost:8000"
        info "API docs: http://localhost:8000/docs"
        cd "$SCRIPT_DIR/backend"
        .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
        ;;

    3)
        printf "\n"
        info "Frontend URL: http://localhost:1420"
        cd "$SCRIPT_DIR/frontend"
        npm run dev
        ;;

    4)
        printf "\n"
        cd "$SCRIPT_DIR/backend"
        .venv/bin/python3 -m pytest tests/ -v --tb=short 2>&1 | head -60
        printf "\n"
        ok "Tests completed"
        ;;

    *)
        warn "Invalid option. Starting backend only..."
        cd "$SCRIPT_DIR/backend"
        .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
        ;;
esac
