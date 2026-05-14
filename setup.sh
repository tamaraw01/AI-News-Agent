#!/bin/bash
# setup.sh — install system dependencies untuk AI News Agent Pro

set -e

YELLOW='\033[1;33m'; GREEN='\033[0;32m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'

echo -e "${CYAN}🔧 AI News Agent Pro — Setup${NC}"

# Check if we can use sudo
USE_SUDO=""
if command -v sudo &>/dev/null && sudo -n true 2>/dev/null; then
  USE_SUDO="sudo"
fi

# Optional dependency installation
install_optional() {
  local cmd="$1"
  local pkg="$2"
  
  if ! command -v "$cmd" &>/dev/null; then
    if [ -n "$USE_SUDO" ]; then
      echo -e "${YELLOW}📦 Installing $pkg...${NC}"
      $USE_SUDO apt install -y "$pkg" -qq 2>/dev/null || echo -e "${YELLOW}⚠️  Could not install $pkg (optional)${NC}"
    else
      echo -e "${YELLOW}⚠️  $pkg not found. Install with: apt install $pkg${NC}"
    fi
  else
    echo -e "${GREEN}✅ $cmd already installed${NC}"
  fi
}

# Check Python
if ! command -v python3.11 &>/dev/null && ! command -v python3 &>/dev/null; then
  echo -e "${RED}❌ Python 3.11+ required${NC}"
  exit 1
fi
echo -e "${GREEN}✅ Python found: $(python3 --version)${NC}"

# Optional system packages
if [ -n "$USE_SUDO" ]; then
  echo -e "${YELLOW}📦 Updating package manager...${NC}"
  $USE_SUDO apt update -qq 2>/dev/null || true
fi

install_optional "tmux" "tmux"
install_optional "git" "git"
install_optional "sqlite3" "sqlite3"

echo ""
echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Setup Complete! ✅                   ║${NC}"
echo -e "${GREEN}╠════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║ Next steps:                            ║${NC}"
echo -e "${GREEN}║ 1. cp .env.example .env                ║${NC}"
echo -e "${GREEN}║ 2. nano .env  (edit API keys)          ║${NC}"
echo -e "${GREEN}║ 3. bash run.sh start                   ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"