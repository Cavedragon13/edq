#!/bin/bash
# LTX-Video-0.9.8-13B — 7-step distilled T2V+I2V with 3-pass upscale
# Port: 8028
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="LTX-Video 0.9.8-13B"
PORT=8028
VENV="venv_ltxvideo"
SCRIPT="scripts/ltxvideo_gradio.py"
MODEL_DIR="models/ltxvideo_098"

service_header "$SERVICE_NAME" "$PORT"

if [ ! -d "$MODEL_DIR" ]; then
    echo "❌ LTX-Video models not found at: $MODEL_DIR"
    echo ""
    echo "   Run the download script first:"
    echo "   bash scripts/download_ltxvideo_models.sh"
    echo ""
    exit 1
fi

gpu_preflight "$PORT"
activate_venv "$VENV"
set_pytorch_env

echo "🚀 Starting $SERVICE_NAME..."

if pgrep -f "ltxvideo_gradio.py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup python "$SCRIPT" > /tmp/ltxvideo.log 2>&1 &
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 60; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Service did not start in time — check /tmp/ltxvideo.log"
        tail -10 /tmp/ltxvideo.log
        exit 1
    fi
fi
