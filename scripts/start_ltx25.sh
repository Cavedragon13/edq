#!/bin/bash
# LTX-2.5 — Lightricks audio+video generation (distilled GGUF, diffusers, non-Comfy)
# Port: 8063
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

# Honest footprint: Q3_K_M GGUF transformer (~13GB resident) + activations.
# Text encoder runs 4-bit and is freed before denoising, so peak is the
# transformer phase. Measured after first real generation — adjust if needed.
TOOL_NAME="ltx25"
REQ_VRAM_MIB=14500
REQ_RAM_MIB=12000
source scripts/vram_guard.sh

SERVICE_NAME="LTX-2.5"
PORT=8063
VENV="venv_ltx25"
GGUF_FILE="/srv/containers/edq/models/ltx25/LTX-2.5-Distilled-Q3_K_M.gguf"
COMPONENTS_DIR="/srv/containers/edq/models/ltx25/LTX-2.5-Diffusers"

service_header "$SERVICE_NAME" "$PORT"

if [ ! -f "$GGUF_FILE" ]; then
    echo "❌ GGUF transformer not found: $GGUF_FILE"
    echo "   Run: bash scripts/download_ltx25_models.sh"
    exit 1
fi
if [ ! -f "$COMPONENTS_DIR/model_index.json" ]; then
    echo "❌ Diffusers components not found: $COMPONENTS_DIR"
    echo "   Accept license at https://huggingface.co/Lightricks/LTX-2.5-Diffusers"
    echo "   then run: bash scripts/download_ltx25_models.sh"
    exit 1
fi

vram_preflight || exit 1
clear_port "$PORT"
activate_venv "$VENV"
set_pytorch_env

echo "🚀 Starting $SERVICE_NAME..."
if pgrep -f "ltx25_server.py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup python scripts/ltx25_server.py > /tmp/ltx25.log 2>&1 &
    register_tool $!
    echo "⏳ Waiting for service (model load takes a while)..."
    if wait_for_port "$PORT" 300; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Not up in time — check /tmp/ltx25.log"
        tail -15 /tmp/ltx25.log
        exit 1
    fi
fi
