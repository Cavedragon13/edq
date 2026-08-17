#!/bin/bash
# MiniMax Music 3 — full-song text-to-music generation (lyrics + music description)
# Port: 8059
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

TOOL_NAME="minimax_music3"
REQ_VRAM_MIB=9000          # ~8GB documented peak with LM group-offload, +headroom
REQ_RAM_MIB=18000          # ~17GB LLM (bf16) sits in CPU RAM while group-offloaded
source scripts/vram_guard.sh

SERVICE_NAME="MiniMax Music 3"
PORT=8059
VENV="venv_minimax_music3"
MODELS_DIR="/srv/containers/edq/models/minimax-music3"
OUTPUT_DIR="$HOME/ai_generated/minimax-music3"

service_header "$SERVICE_NAME" "$PORT"

if [ ! -f "$MODELS_DIR/model_index.json" ]; then
    echo "❌ Model not found: $MODELS_DIR"
    echo "   Run: bash scripts/download_minimax_music3_models.sh"
    exit 1
fi

vram_preflight || exit 1   # refuses if short; relaunch with CLEAR=1 to free registered tools
clear_port "$PORT"
activate_venv "$VENV"
set_pytorch_env

mkdir -p "$OUTPUT_DIR"

echo "🚀 Starting $SERVICE_NAME..."
if pgrep -f "minimax_music3_server.py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup python scripts/minimax_music3_server.py > /tmp/minimax_music3.log 2>&1 &
    register_tool $!
    echo "⏳ Waiting for service (model load can take a couple minutes)..."
    if wait_for_port "$PORT" 180; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Not up in time — check /tmp/minimax_music3.log"
        tail -30 /tmp/minimax_music3.log
        exit 1
    fi
fi
