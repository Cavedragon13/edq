#!/bin/bash
# HiDream-O1-Image-Dev — Pixel-level unified T2I, editing, subject-driven generation
# Port: 8052
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="HiDream-O1-Image-Dev"
PORT=8052
VENV="venv_hidream_o1"
APP_DIR="$DRAGONSUITE_ROOT/projects/hidream-o1"
MODEL_PATH="/srv/containers/edq/models/hidream-o1-dev"

service_header "$SERVICE_NAME" "$PORT"

if [ ! -d "$APP_DIR" ]; then
    echo "❌ Project not found: $APP_DIR"
    echo "   git clone https://github.com/HiDream-ai/HiDream-O1-Image projects/hidream-o1"
    exit 1
fi

if [ ! -f "$MODEL_PATH/config.json" ]; then
    echo "❌ Model not found at $MODEL_PATH"
    echo "   Run: bash scripts/download_hidream_o1_models.sh"
    exit 1
fi

gpu_preflight "$PORT"
activate_venv "$VENV"
set_pytorch_env

export HIDREAM_PORT=$PORT
export HIDREAM_HOST=0.0.0.0
# Flash-attn disabled — sm_120 (Blackwell) not supported; patched in models/pipeline.py
export FA_VERSION=disabled
# Prompt Agent → Ollama (OpenAI-compatible)
export OPENAI_BASE_URL=http://localhost:11434/v1
export OPENAI_API_KEY=ollama
export OPENAI_MODEL=gemma4:e4b

echo "🚀 Starting $SERVICE_NAME on port $PORT..."
cd "$APP_DIR"
nohup python app.py \
    --model_path "$MODEL_PATH" \
    --model_type dev \
    --host 0.0.0.0 \
    --port $PORT \
    > /tmp/hidream_o1.log 2>&1 &

echo "⏳ Loading 8B model into VRAM (may take 30-60s)..."
if wait_for_port "$PORT" 180; then
    echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
else
    echo "❌ Not up in time — check /tmp/hidream_o1.log"
    tail -20 /tmp/hidream_o1.log
    exit 1
fi
