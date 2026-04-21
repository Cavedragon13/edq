#!/bin/bash
# Unsloth Studio — LLM fine-tuning web UI
# Port: 8050
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="Unsloth Studio"
PORT=8050
VENV="venv_unsloth_studio"
LOG="/tmp/unsloth_studio.log"

service_header "$SERVICE_NAME" "$PORT"

activate_venv "$VENV"

if pgrep -f "unsloth studio run" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    echo "🚀 Starting $SERVICE_NAME..."
    nohup unsloth studio -H 0.0.0.0 -p "$PORT" > "$LOG" 2>&1 &
    if wait_for_port "$PORT" 60; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Failed — check $LOG"
        tail -20 "$LOG"
        exit 1
    fi
fi
