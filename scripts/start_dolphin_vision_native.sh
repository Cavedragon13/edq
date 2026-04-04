#!/bin/bash
# Dolphin Vision 7B — Uncensored VLM (native UI)
# Port: 8025 | /analyze endpoint preserved for Dragonsight 4 integration
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="Dolphin Vision 7B"
PORT=8025
VENV="venv_dolphin_vision"
SCRIPT="scripts/dolphin_vision_server.py"

service_header "$SERVICE_NAME" "$PORT"
gpu_preflight "$PORT"
activate_venv "$VENV"
set_pytorch_env

echo "🚀 Starting $SERVICE_NAME..."
if pgrep -f "dolphin_vision_server.py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup python "$SCRIPT" > /tmp/dolphin_vision.log 2>&1 &
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 60; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Service did not start in time — check /tmp/dolphin_vision.log"
        tail -10 /tmp/dolphin_vision.log
        exit 1
    fi
fi
