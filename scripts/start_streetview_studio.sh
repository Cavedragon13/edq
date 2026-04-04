#!/bin/bash
# Street View Studio — fetch + AI-transform Google Street View images via FLUX.1-schnell
# Port: 8040
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="Street View Studio"
PORT=8040
VENV="venv_flux2"
SCRIPT="scripts/streetview_studio_gradio.py"
MODEL_DIR="/srv/containers/edq/models/flux1-schnell"

service_header "$SERVICE_NAME" "$PORT"
gpu_preflight "$PORT"
activate_venv "$VENV"
set_pytorch_env

# Model check — fail fast before wasting time
if [ ! -f "$MODEL_DIR/model_index.json" ]; then
    echo "❌ FLUX.1-schnell not found at $MODEL_DIR"
    echo "   Run first: bash scripts/download_flux1_schnell.sh"
    exit 1
fi
echo "✓ Models found"
echo ""

echo "🚀 Starting $SERVICE_NAME..."

if pgrep -f "streetview_studio_gradio.py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup python "$SCRIPT" > /tmp/streetview_studio.log 2>&1 &
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 30; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Failed — check /tmp/streetview_studio.log"
        tail -10 /tmp/streetview_studio.log
        exit 1
    fi
fi
