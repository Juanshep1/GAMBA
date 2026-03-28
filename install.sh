#!/bin/bash
# ============================================
#  GAMBA - Universal One-Line Installer
#  Works on: macOS, Linux, Android (Termux),
#            iOS (a-Shell/iSH)
#
#  Usage:
#    bash <(curl -sL https://raw.githubusercontent.com/Juanshep1/GAMBA/main/install.sh)
#
#  Or if already cloned:
#    bash install.sh
# ============================================

set -e

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
DIM='\033[2m'
BOLD='\033[1m'
NC='\033[0m'

echo ""
echo -e "${CYAN}${BOLD}  ██████   █████  ███    ███ ██████   █████ ${NC}"
echo -e "${CYAN}${BOLD} ██       ██   ██ ████  ████ ██   ██ ██   ██${NC}"
echo -e "${CYAN}${BOLD} ██   ███ ███████ ██ ████ ██ ██████  ███████${NC}"
echo -e "${CYAN}${BOLD} ██    ██ ██   ██ ██  ██  ██ ██   ██ ██   ██${NC}"
echo -e "${CYAN}${BOLD}  ██████  ██   ██ ██      ██ ██████  ██   ██${NC}"
echo ""
echo -e "${DIM} Lightweight Multi-Agent Framework${NC}"
echo ""

# ---- Detect platform ----
PLATFORM="unknown"
DEVICE="desktop"
PKG_CMD=""

if [ -n "$TERMUX_VERSION" ] || [ -d "/data/data/com.termux" ]; then
    PLATFORM="android"
    DEVICE="termux"
    PKG_CMD="pkg"
    echo -e "${GREEN}Detected: Android (Termux)${NC}"
elif [ -d "/var/mobile" ] || [ -n "$ASHELL" ]; then
    PLATFORM="ios"
    DEVICE="ashell"
    echo -e "${GREEN}Detected: iOS (a-Shell)${NC}"
elif [ -e "/dev/ish" ]; then
    PLATFORM="ios"
    DEVICE="ish"
    PKG_CMD="apk"
    echo -e "${GREEN}Detected: iOS (iSH)${NC}"
elif [ "$(uname)" = "Darwin" ]; then
    PLATFORM="macos"
    echo -e "${GREEN}Detected: macOS $(uname -m)${NC}"
elif [ "$(uname)" = "Linux" ]; then
    PLATFORM="linux"
    if command -v apt >/dev/null 2>&1; then
        PKG_CMD="apt"
    elif command -v dnf >/dev/null 2>&1; then
        PKG_CMD="dnf"
    elif command -v pacman >/dev/null 2>&1; then
        PKG_CMD="pacman"
    fi
    echo -e "${GREEN}Detected: Linux $(uname -m)${NC}"
fi
echo ""

# ---- Install system dependencies ----
echo -e "${BOLD}[1/5] Installing system dependencies...${NC}"

if [ "$DEVICE" = "termux" ]; then
    pkg update -y 2>/dev/null
    pkg install -y python git 2>/dev/null
elif [ "$DEVICE" = "ish" ]; then
    apk add python3 py3-pip git 2>/dev/null
elif [ "$PLATFORM" = "macos" ]; then
    if ! command -v python3 >/dev/null 2>&1; then
        echo -e "${YELLOW}Python3 not found. Install with: brew install python3${NC}"
        exit 1
    fi
    if ! command -v git >/dev/null 2>&1; then
        echo -e "${YELLOW}Git not found. Install with: xcode-select --install${NC}"
        exit 1
    fi
    echo -e "${DIM}  python3 and git already available${NC}"
elif [ "$PLATFORM" = "linux" ]; then
    if ! command -v python3 >/dev/null 2>&1; then
        if [ "$PKG_CMD" = "apt" ]; then
            sudo apt update && sudo apt install -y python3 python3-pip git
        elif [ "$PKG_CMD" = "dnf" ]; then
            sudo dnf install -y python3 python3-pip git
        elif [ "$PKG_CMD" = "pacman" ]; then
            sudo pacman -Sy --noconfirm python python-pip git
        fi
    fi
    echo -e "${DIM}  python3 and git available${NC}"
fi

# ---- Clone GAMBA ----
echo -e "${BOLD}[2/5] Getting GAMBA...${NC}"

INSTALL_DIR="$HOME/gamba"

if [ -d "$INSTALL_DIR/.git" ]; then
    echo -e "${DIM}  Updating existing install...${NC}"
    cd "$INSTALL_DIR"
    git pull --ff-only 2>/dev/null || true
elif [ -f "pyproject.toml" ] && grep -q "gamba" pyproject.toml 2>/dev/null; then
    # Already in the GAMBA directory
    INSTALL_DIR="$(pwd)"
    echo -e "${DIM}  Using current directory${NC}"
else
    git clone https://github.com/Juanshep1/GAMBA.git "$INSTALL_DIR" 2>/dev/null || {
        echo -e "${YELLOW}  Clone failed - if repo is private, clone manually first${NC}"
        echo -e "${YELLOW}  git clone https://github.com/Juanshep1/GAMBA.git ~/gamba${NC}"
        exit 1
    }
    cd "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

# ---- Install Python dependencies ----
echo -e "${BOLD}[3/5] Installing Python packages...${NC}"

if [ "$DEVICE" = "termux" ]; then
    # Lightweight install for Termux
    pip install aiohttp pyyaml pydantic rich duckduckgo-search 2>/dev/null
    # Textual is optional on Termux (heavy)
    echo -e "${DIM}  Core deps installed. For TUI: pip install textual${NC}"
elif [ "$DEVICE" = "ashell" ]; then
    pip install aiohttp pyyaml pydantic rich 2>/dev/null
    echo -e "${DIM}  Core deps installed (minimal for iOS)${NC}"
elif [ "$DEVICE" = "ish" ]; then
    pip3 install aiohttp pyyaml pydantic rich duckduckgo-search 2>/dev/null
else
    # Desktop: install everything
    pip3 install -e ".[tui,search]" 2>/dev/null || pip install -e ".[tui,search]" 2>/dev/null || {
        pip3 install aiohttp pyyaml pydantic rich textual duckduckgo-search 2>/dev/null
    }
fi

# ---- Configure ----
echo -e "${BOLD}[4/5] Configuring GAMBA...${NC}"

mkdir -p data agents

# Copy default agents if not present
if [ ! -f agents/researcher.yaml ] && [ -f agents/example_researcher.yaml ]; then
    echo -e "${DIM}  Default agents ready${NC}"
fi

# Auto-detect local models
echo -e "${DIM}  Scanning for local AI models...${NC}"
python3 -c "
import asyncio
from gamba.core.detect import detect_all
r = asyncio.run(detect_all())
p = r.platform
print(f'  Platform: {p.os}/{p.device} ({p.arch})')
if r.local_models:
    print(f'  Found {len(r.local_models)} local models:')
    for m in r.local_models[:5]:
        print(f'    - {m.name} [{m.provider}] {m.size}')
else:
    print('  No local models found (cloud-only mode)')
for rec in r.recommendations[:3]:
    print(f'  * {rec}')
" 2>/dev/null || echo -e "${DIM}  Detection skipped${NC}"

# Create config if it doesn't exist
if [ ! -f data/config.yaml ]; then
    echo ""
    echo -e "${BOLD}First-time setup - need your API key:${NC}"
    echo ""
    echo -e "  ${DIM}Get one free at: https://openrouter.ai${NC}"
    echo ""
    read -p "  OpenRouter API key (or press Enter to skip): " API_KEY

    if [ -z "$API_KEY" ]; then
        # Check if Ollama is running
        if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
            echo -e "${GREEN}  No API key - using local Ollama as default${NC}"
            cat > data/config.yaml << CONF
version: 1
default_provider: ollama
providers:
  ollama:
    api_key: ''
    api_token: ''
    base_url: http://localhost:11434
    default_model: llama3.2:3b
interfaces:
  tui:
    enabled: true
    bot_token: ''
    port: 8420
  telegram:
    enabled: false
    bot_token: ''
    port: 8420
  discord:
    enabled: false
    bot_token: ''
    port: 8420
  web:
    enabled: true
    bot_token: ''
    port: 8420
agents_dir: ./agents
data_dir: ./data
CONF
        else
            echo -e "${YELLOW}  No API key and no local models - run 'python3 -m gamba --setup' later${NC}"
            cat > data/config.yaml << CONF
version: 1
default_provider: openrouter
providers: {}
interfaces:
  tui:
    enabled: true
    bot_token: ''
    port: 8420
  telegram:
    enabled: false
    bot_token: ''
    port: 8420
  discord:
    enabled: false
    bot_token: ''
    port: 8420
  web:
    enabled: false
    bot_token: ''
    port: 8420
agents_dir: ./agents
data_dir: ./data
CONF
        fi
    else
        # Check for Ollama too
        OLLAMA_BLOCK=""
        if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
            OLLAMA_BLOCK="
  ollama:
    api_key: ''
    api_token: ''
    base_url: http://localhost:11434
    default_model: llama3.2:3b"
            echo -e "${GREEN}  Ollama detected - added as secondary provider${NC}"
        fi

        cat > data/config.yaml << CONF
version: 1
default_provider: openrouter
providers:
  openrouter:
    api_key: ${API_KEY}
    api_token: ''
    base_url: ''
    default_model: google/gemini-2.0-flash-001${OLLAMA_BLOCK}
interfaces:
  tui:
    enabled: true
    bot_token: ''
    port: 8420
  telegram:
    enabled: false
    bot_token: ''
    port: 8420
  discord:
    enabled: false
    bot_token: ''
    port: 8420
  web:
    enabled: true
    bot_token: ''
    port: 8420
agents_dir: ./agents
data_dir: ./data
CONF
        echo -e "${GREEN}  Config saved with OpenRouter${NC}"
    fi
else
    echo -e "${DIM}  Config already exists${NC}"
fi

# ---- Done ----
echo ""
echo -e "${BOLD}[5/5] Done!${NC}"
echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  GAMBA installed at: ${INSTALL_DIR}${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "  Run GAMBA:"
echo ""
echo -e "    ${CYAN}cd ${INSTALL_DIR}${NC}"
echo -e "    ${CYAN}python3 -m gamba${NC}              ${DIM}# TUI dashboard${NC}"
echo -e "    ${CYAN}python3 -m gamba --no-tui${NC}     ${DIM}# simple console${NC}"
echo -e "    ${CYAN}python3 -m gamba \"hello\"${NC}      ${DIM}# one-shot test${NC}"
echo ""
echo -e "  Reconfigure:  ${CYAN}python3 -m gamba --setup${NC}"
echo ""

# Ask if they want to launch now
read -p "  Launch GAMBA now? [Y/n]: " LAUNCH
LAUNCH=${LAUNCH:-Y}
if [ "$LAUNCH" = "Y" ] || [ "$LAUNCH" = "y" ]; then
    cd "$INSTALL_DIR"
    if [ "$DEVICE" = "termux" ]; then
        python3 -m gamba --no-tui
    else
        python3 -m gamba --no-tui
    fi
fi
