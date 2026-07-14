#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
BACKEND="$SCRIPT_DIR/backend"
PYTHON="$VENV_DIR/bin/python3"

# Port is configurable via env; keep default in sync with backend/server.py
PORT="${DASHBOARD_PORT:-8666}"

# Auto-setup if venv doesn't exist yet
if [ ! -f "$PYTHON" ]; then
    echo "⚠ venv not found — running setup first..."
    echo ""
    bash "$SCRIPT_DIR/setup.sh"
    echo ""
fi

echo "┌──────────────────────────────────────────────┐"
echo "│  AI Workstation Dashboard                     │"
echo "│  http://localhost:$PORT"
echo "│  http://$(hostname -I | awk '{print $1}'):$PORT"
echo "│  Press Ctrl+C to stop                         │"
echo "└──────────────────────────────────────────────┘"
echo ""

cd "$BACKEND"
exec "$PYTHON" server.py
