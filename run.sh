#!/bin/bash
# run.sh — jalankan AI News Agent Pro di Linux tanpa Docker

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
LOG_DIR="$PROJECT_DIR/logs"
DATA_DIR="$PROJECT_DIR/data"

# Warna output
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

mkdir -p "$LOG_DIR" "$DATA_DIR/chroma" "$DATA_DIR/sqlite"

# --- Fungsi ---
find_python() {
  if command -v python3.11 &>/dev/null; then
    echo "python3.11"
  elif command -v python3.12 &>/dev/null; then
    echo "python3.12"
  elif command -v python3 &>/dev/null; then
    echo "python3"
  else
    return 1
  fi
}

check_deps() {
  echo -e "${CYAN}🔍 Mengecek dependencies...${NC}"
  PYTHON_CMD=$(find_python) || { echo -e "${RED}Python 3+ tidak ditemukan${NC}"; exit 1; }
  echo -e "${GREEN}✅ Python: $($PYTHON_CMD --version)${NC}"
  command -v tmux &>/dev/null || { echo -e "${YELLOW}tmux tidak ada, install dulu: sudo apt install tmux${NC}"; exit 1; }
}

setup_venv() {
  if [ ! -d "$VENV_DIR" ]; then
    echo -e "${CYAN}📦 Membuat virtual environment...${NC}"
    PYTHON_CMD=$(find_python)
    # Create venv without pip (ensurepip may fail on some systems)
    $PYTHON_CMD -m venv "$VENV_DIR" --without-pip
    
    # Install pip using get-pip.py
    echo -e "${CYAN}📦 Installing pip...${NC}"
    curl -sS https://bootstrap.pypa.io/get-pip.py | "$VENV_DIR/bin/python" 2>/dev/null || {
      echo -e "${YELLOW}⚠️  get-pip.py failed, trying ensurepip...${NC}"
      "$VENV_DIR/bin/python" -m ensurepip --upgrade || true
    }
  fi
  
  source "$VENV_DIR/bin/activate"
  echo -e "${CYAN}📦 Install dependencies...${NC}"
  pip install -q --upgrade pip setuptools wheel
  pip install -q -r requirements.txt 2>/dev/null || pip install -q --break-system-packages -r requirements.txt
  python -m spacy download en_core_web_sm -q 2>/dev/null || true
}

check_env() {
  if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo -e "${YELLOW}⚠️  File .env tidak ditemukan. Menyalin dari .env.example...${NC}"
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    echo -e "${RED}❗ Edit .env dan isi API keys, lalu jalankan ulang.${NC}"
    exit 1
  fi
}

init_db() {
  echo -e "${CYAN}🗄️  Inisialisasi database...${NC}"
  source "$VENV_DIR/bin/activate"
  python3 -c "
import asyncio
from core.database import init_db
asyncio.run(init_db())
print('Database siap.')
"
}

start_services() {
  SESSION="ai-news-agent"
  tmux kill-session -t "$SESSION" 2>/dev/null || true
  tmux new-session -d -s "$SESSION" -x 220 -y 50

  # Window 1: Telegram bot + ingestion scheduler
  tmux rename-window -t "$SESSION:0" "telegram"
  tmux send-keys -t "$SESSION:telegram" \
    "source $VENV_DIR/bin/activate && cd $PROJECT_DIR && \
     python main.py 2>&1 | tee $LOG_DIR/telegram.log" Enter

  # Window 2: Logs monitor
  tmux new-window -t "$SESSION" -n "logs"
  tmux send-keys -t "$SESSION:logs" \
    "tail -f $LOG_DIR/*.log" Enter

  tmux select-window -t "$SESSION:telegram"
}

stop_services() {
  echo -e "${YELLOW}🛑 Menghentikan semua service...${NC}"
  tmux kill-session -t "ai-news-agent" 2>/dev/null || true
  echo -e "${GREEN}✅ Semua service dihentikan.${NC}"
}

status_services() {
  echo -e "${CYAN}📊 Status services:${NC}"
  tmux has-session -t ai-news-agent 2>/dev/null \
    && echo -e "${GREEN}✅ Telegram bot + worker: berjalan di tmux session${NC}" \
    || echo -e "${RED}❌ Telegram bot + worker: tidak berjalan${NC}"
}

# --- Main ---
case "${1:-start}" in
  start)
    check_deps
    check_env
    setup_venv
    init_db
    start_services
    sleep 3
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║   AI News Agent Pro — RUNNING ✅     ║${NC}"
    echo -e "${GREEN}╠══════════════════════════════════════╣${NC}"
    echo -e "${GREEN}║  Output     →  Telegram bot          ║${NC}"
    echo -e "${GREEN}║  tmux attach→  tmux a -t ai-news-agent ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
    ;;
  stop)   stop_services ;;
  status) status_services ;;
  restart) stop_services; sleep 2; bash "$0" start ;;
  logs)   tmux attach-session -t ai-news-agent ;;
  install)
    check_deps; check_env; setup_venv; init_db
    echo -e "${GREEN}✅ Instalasi selesai. Jalankan: bash run.sh start${NC}"
    ;;
  *)
    echo "Usage: bash run.sh [start|stop|status|restart|logs|install]"
    ;;
esac
