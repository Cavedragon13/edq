#!/bin/bash
# UniForge3D Studio — sparse unposed multi-view images → textured GLB
# Port: 8075.  Non-commercial weights (CC BY-NC 4.0 VGGT-derived + RMBG-2.0).
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

# Measured 2026-10-18 (4 views, seed 1, low_vram): peak ~13.1GB VRAM and ~23.7GB RAM above idle; ~7 min.
# Tight on 16GB: a random-seed run once OOMed in mesh post-processing -- just retry or use another seed.
TOOL_NAME="uniforge3d"
REQ_VRAM_MIB=13500
REQ_RAM_MIB=24000
source scripts/vram_guard.sh

SERVICE_NAME="UniForge3D Studio"
PORT=8075
VENV="venv_uniforge3d"
APP_DIR="$DRAGONSUITE_ROOT/projects/UniForge3D"
MODEL_DIR="$DRAGONSUITE_ROOT/models/uniforge3d"

service_header "$SERVICE_NAME" "$PORT"

if [ ! -d "$APP_DIR/uniforge3d" ]; then
    echo "❌ Project not found: $APP_DIR"
    echo "   git clone https://github.com/xibushu/UniForge3D.git projects/UniForge3D"
    exit 1
fi
if [ ! -x "$DRAGONSUITE_ROOT/$VENV/bin/python" ]; then
    echo "❌ venv missing — run: bash scripts/setup_uniforge3d_env.sh"
    exit 1
fi
if [ ! -f "$MODEL_DIR/pipeline.json" ]; then
    echo "❌ Models not found — run: bash scripts/download_uniforge3d_models.sh"
    exit 1
fi

vram_preflight || exit 1
clear_port "$PORT"
activate_venv "$VENV"
set_pytorch_env
mkdir -p /home/edq/ai_generated/uniforge3d

echo "🚀 Starting $SERVICE_NAME..."
if pgrep -f "[u]niforge3d_server.py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    setsid nohup python scripts/uniforge3d_server.py < /dev/null > /tmp/uniforge3d.log 2>&1 &
    register_tool $!
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 90; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Not up in time — check /tmp/uniforge3d.log"
        tail -30 /tmp/uniforge3d.log
        exit 1
    fi
fi
