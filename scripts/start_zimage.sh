#!/bin/bash
# Z-Image Base — Alibaba Tongyi 6B Text-to-Image
# Port: 8011
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="Z-Image Base"
PORT=8011
VENV="venv_zimage"
SCRIPT="scripts/zimage_base_gradio.py"

service_header "$SERVICE_NAME" "$PORT"
gpu_preflight "$PORT"
activate_venv "$VENV"
set_pytorch_env

echo "🚀 Starting $SERVICE_NAME..."
mkdir -p "$HOME/ai_generated/zimage"

if pgrep -f "zimage_base_gradio.py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup python "$SCRIPT" > /tmp/zimage.log 2>&1 &
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 30; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Service did not start in time — check /tmp/zimage.log"
        tail -10 /tmp/zimage.log
        exit 1
    fi
fi
