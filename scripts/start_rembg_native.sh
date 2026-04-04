#!/bin/bash
# Rembg — AI background removal
# Port: 8012
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="Rembg"
PORT=8012
VENV="venv_rembg"
SCRIPT="scripts/rembg_server.py"

service_header "$SERVICE_NAME" "$PORT"
gpu_preflight "$PORT"
activate_venv "$VENV"
pip install -q fastapi uvicorn python-multipart 2>/dev/null || true
set_pytorch_env

mkdir -p "$HOME/ai_generated/rembg"
echo "🚀 Starting $SERVICE_NAME..."

if pgrep -f "rembg_server.py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup python "$SCRIPT" > /tmp/rembg.log 2>&1 &
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 30; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Service did not start in time — check /tmp/rembg.log"
        tail -10 /tmp/rembg.log
        exit 1
    fi
fi
