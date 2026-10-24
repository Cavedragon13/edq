#!/bin/bash
# Z-Anime — Anime fine-tune of Z-Image Base (6B, S3-DiT, SeeSee21)
# Port: 8008
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

# Honest footprint (vram_guard). Measured 2026-10-24: sequential_cpu_offload
# keeps the GPU footprint tiny (peak ~2.2GB) and stages weights in system RAM
# instead (server RSS peaked ~12.2GB during a real 832x1216/40-step generation).
TOOL_NAME="zanime"
REQ_VRAM_MIB=2700
REQ_RAM_MIB=13000
source scripts/vram_guard.sh

SERVICE_NAME="Z-Anime"
PORT=8008
VENV="venv_zimage"
SCRIPT="scripts/zanime_gradio.py"
DIFFUSERS_DIR="/srv/containers/edq/models/zanime/diffusers"

service_header "$SERVICE_NAME" "$PORT"

# Fail-fast model check BEFORE vram_preflight (cheaper to fail early)
if [ ! -f "$DIFFUSERS_DIR/model_index.json" ]; then
    echo "❌ Z-Anime diffusers model not found at $DIFFUSERS_DIR"
    echo "   Run: bash scripts/download_zanime_models.sh"
    exit 1
fi

vram_preflight || exit 1
clear_port "$PORT"
activate_venv "$VENV"
set_pytorch_env

mkdir -p "$HOME/ai_generated/zanime"

echo "🚀 Starting $SERVICE_NAME..."
if pgrep -f "zanime_gradio.py" > /dev/null; then
    if curl -s --max-time 2 "http://127.0.0.1:$PORT/" > /dev/null 2>&1; then
        echo "✓ Already running on port $PORT"
    else
        echo "⚠️  Found stale Z-Anime process without a listening port; stopping it..."
        pkill -f "zanime_gradio.py" || true
        sleep 2
        nohup python "$SCRIPT" > /tmp/zanime.log 2>&1 &
        register_tool $!
        echo "⏳ Waiting for service..."
        if wait_for_port "$PORT" 120; then
            echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
        else
            echo "❌ Not up in time — check /tmp/zanime.log"
            tail -15 /tmp/zanime.log
            exit 1
        fi
    fi
else
    nohup python "$SCRIPT" > /tmp/zanime.log 2>&1 &
    register_tool $!
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 120; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Not up in time — check /tmp/zanime.log"
        tail -15 /tmp/zanime.log
        exit 1
    fi
fi
