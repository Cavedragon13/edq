#!/bin/bash
# TripoSplat Studio — image → 3D Gaussian splat with mask/preview/approve step
# Port: 8067
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

# Honest footprint — measured 2026-09-24 with nvidia-smi (see docs/venvs.md).
TOOL_NAME="triposplat"
REQ_VRAM_MIB=6000          # measured peak ~5.0GB (6.1GB total incl. 1.1GB desktop baseline), 262k gaussians
REQ_RAM_MIB=6000
source scripts/vram_guard.sh

SERVICE_NAME="TripoSplat Studio"
PORT=8067
VENV="venv_triposplat"
APP_DIR="$DRAGONSUITE_ROOT/projects/TripoSplat"
CKPT_DIR="$DRAGONSUITE_ROOT/models/triposplat"

service_header "$SERVICE_NAME" "$PORT"

if [ ! -f "$APP_DIR/triposplat.py" ]; then
    echo "❌ Project not found: $APP_DIR"
    echo "   git clone https://github.com/VAST-AI-Research/TripoSplat.git projects/TripoSplat"
    exit 1
fi
if [ ! -f "$CKPT_DIR/diffusion_models/triposplat_fp16.safetensors" ] || [ ! -f "$CKPT_DIR/clip_vision/dino_v3_vit_h.safetensors" ]; then
    echo "❌ Models not found in $CKPT_DIR"
    echo "   Run: bash scripts/download_triposplat_models.sh"
    exit 1
fi

vram_preflight || exit 1
clear_port "$PORT"
activate_venv "$VENV"
set_pytorch_env

mkdir -p /home/edq/ai_generated/triposplat

echo "🚀 Starting $SERVICE_NAME..."
if pgrep -f "python scripts/triposplat_server[.]py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup python scripts/triposplat_server.py > /tmp/triposplat.log 2>&1 &
    register_tool $!
    echo "⏳ Waiting for service (model load ~30s)..."
    if wait_for_port "$PORT" 180; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Not up in time — check /tmp/triposplat.log"
        tail -15 /tmp/triposplat.log
        exit 1
    fi
fi
