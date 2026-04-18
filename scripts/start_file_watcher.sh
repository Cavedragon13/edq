#!/bin/bash
# Dragon File Watcher — Background daemon, scans every 3h
# No GPU required — uses Ollama (always-on)
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="Dragon File Watcher"
VENV="venv_dragonsuite"
SCRIPT="scripts/file_watcher.py"
LOG="/tmp/file_watcher.log"

service_header "$SERVICE_NAME" ""
activate_venv "$VENV"

if ! curl -s http://127.0.0.1:11434/api/tags > /dev/null 2>&1; then
    echo "❌ Ollama is not running on port 11434"
    exit 1
fi

if pgrep -f "file_watcher.py" > /dev/null 2>&1; then
    echo "✓ Already running (PID $(pgrep -f file_watcher.py))"
    exit 0
fi

echo "🚀 Starting $SERVICE_NAME..."
nohup python3 "$SCRIPT" > "$LOG" 2>&1 &
echo "✅ $SERVICE_NAME started (PID $!) — logs at $LOG"
