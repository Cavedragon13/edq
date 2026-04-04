#!/bin/bash
# Real-ESRGAN — AI upscaling with multiple models
# Port: 8010
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="Real-ESRGAN"
PORT=8010
VENV="venv_realesrgan"
SCRIPT="scripts/realesrgan_server.py"

service_header "$SERVICE_NAME" "$PORT"
gpu_preflight "$PORT"
activate_venv "$VENV"
pip install -q fastapi uvicorn python-multipart 2>/dev/null || true
set_pytorch_env

echo "🚀 Starting $SERVICE_NAME..."

if pgrep -f "realesrgan_server.py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup python "$SCRIPT" > /tmp/realesrgan.log 2>&1 &
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 30; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Service did not start in time — check /tmp/realesrgan.log"
        tail -10 /tmp/realesrgan.log
        exit 1
    fi
fi
