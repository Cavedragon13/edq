#!/bin/bash
# MOSS-Image — 5B DiT text-to-image with strong text rendering + layout control (Gradio)
# Port: 8074
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

# Footprint: sequential CPU offload (scripts/moss_image_app.py). Measured 2026-10-18 at 1024px/50 steps:
# ~1.2GB VRAM above desktop baseline, ~7.6GB RAM above baseline. Component offload OOMs (18GB text encoder).
TOOL_NAME="moss-image"
REQ_VRAM_MIB=3000
REQ_RAM_MIB=12000
source scripts/vram_guard.sh

SERVICE_NAME="MOSS-Image"
PORT=8074
VENV="venv_moss_image"
APP_DIR="$DRAGONSUITE_ROOT/projects/MOSS-Image"
MODEL_ROOT="$DRAGONSUITE_ROOT/models/moss-image"
OUT_DIR="/home/edq/ai_generated/moss-image"

service_header "$SERVICE_NAME" "$PORT"

if [ ! -d "$APP_DIR" ]; then
    echo "❌ Project not found: $APP_DIR"
    echo "   git clone https://github.com/OpenMOSS/MOSS-Image.git projects/MOSS-Image"
    exit 1
fi
if [ ! -f "$MODEL_ROOT/MOSS-Image-SFT/model_index.json" ]; then
    echo "❌ Models not found — run: bash scripts/download_moss_image_models.sh"
    exit 1
fi

vram_preflight || exit 1
clear_port "$PORT"
activate_venv "$VENV"
set_pytorch_env
mkdir -p "$OUT_DIR"

echo "🚀 Starting $SERVICE_NAME..."
if pgrep -f "[m]oss_image_app.py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    setsid nohup python "$DRAGONSUITE_ROOT/scripts/moss_image_app.py" \
        --profile 16gb \
        --model-root "$MODEL_ROOT" \
        --model "$MODEL_ROOT/MOSS-Image-SFT" \
        --local-files-only \
        --output-dir "$OUT_DIR" \
        --host 0.0.0.0 --port "$PORT" \
        < /dev/null > /tmp/moss_image.log 2>&1 &
    register_tool $!
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 120; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Not up in time — check /tmp/moss_image.log"
        tail -30 /tmp/moss_image.log
        exit 1
    fi
fi
