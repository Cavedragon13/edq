#!/bin/bash
# TADA TTS - Hume AI open-source generative speech
# TADA-3B-ML: multilingual voice cloning, 1:1 token alignment
# Port: 8037
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="TADA TTS"
PORT=8037
VENV="venv_tada"
SCRIPT="scripts/tada_gradio.py"

HF_CACHE="${HF_HOME:-$HOME/.cache/huggingface}/hub"
TADA_MODEL_CACHE="$HF_CACHE/models--HumeAI--tada-3b-ml"
CODEC_CACHE="$HF_CACHE/models--HumeAI--tada-codec"

service_header "$SERVICE_NAME" "$PORT"

# Check models downloaded
if [ ! -d "$TADA_MODEL_CACHE" ] || [ ! -d "$CODEC_CACHE" ]; then
    echo "❌ TADA models not found in HuggingFace cache."
    echo ""
    echo "   Run the download script first:"
    echo "   bash scripts/download_tada_models.sh"
    echo ""
    exit 1
fi

gpu_preflight "$PORT"
activate_venv "$VENV"
set_pytorch_env

export GRADIO_SERVER_NAME="0.0.0.0"
export GRADIO_SERVER_PORT="$PORT"

echo "🚀 Starting $SERVICE_NAME..."
if pgrep -f "tada_gradio.py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup python "$SCRIPT" > /tmp/tada.log 2>&1 &
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 30; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Service did not start in time — check /tmp/tada.log"
        tail -10 /tmp/tada.log
        exit 1
    fi
fi
