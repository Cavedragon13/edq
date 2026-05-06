#!/bin/bash
# Z-Anime — Anime fine-tune of Z-Image Base (6B, S3-DiT, SeeSee21)
# Port: 8008
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="Z-Anime"
PORT=8008
VENV="venv_zimage"
SCRIPT="scripts/zanime_gradio.py"
DIFFUSERS_DIR="/srv/containers/edq/models/zanime/diffusers"

service_header "$SERVICE_NAME" "$PORT"

# Fail-fast model check BEFORE gpu_preflight (cheaper to fail early)
if [ ! -f "$DIFFUSERS_DIR/model_index.json" ]; then
    echo "❌ Z-Anime diffusers model not found at $DIFFUSERS_DIR"
    echo "   Run: bash scripts/download_zanime_models.sh"
    exit 1
fi

gpu_preflight "$PORT"
activate_venv "$VENV"
set_pytorch_env

mkdir -p "$HOME/ai_generated/zanime"

echo "🚀 Starting $SERVICE_NAME..."
if pgrep -f "zanime_gradio.py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup python "$SCRIPT" > /tmp/zanime.log 2>&1 &
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 120; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Not up in time — check /tmp/zanime.log"
        tail -15 /tmp/zanime.log
        exit 1
    fi
fi
