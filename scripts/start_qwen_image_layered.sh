#!/bin/bash
# Qwen-Image-Layered — Image layer decomposition for advanced editing
# Port: 8013
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="Qwen-Image-Layered"
PORT=8013
VENV="venv_qwen_image_layered"
SCRIPT="scripts/qwen_image_layered_gradio.py"

service_header "$SERVICE_NAME" "$PORT"
gpu_preflight "$PORT"
activate_venv "$VENV"
set_pytorch_env

mkdir -p "$HOME/ai_generated/qwen-layered"
echo "🚀 Starting $SERVICE_NAME..."
echo "   VRAM: ~14-16GB with CPU offloading"

if pgrep -f "qwen_image_layered_gradio.py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup python "$SCRIPT" > /tmp/qwen_image_layered.log 2>&1 &
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 60; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Service did not start in time — check /tmp/qwen_image_layered.log"
        tail -10 /tmp/qwen_image_layered.log
        exit 1
    fi
fi
