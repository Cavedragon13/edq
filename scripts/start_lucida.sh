#!/bin/bash
# Lucida — Background removal that keeps glass, camouflage, text, glow, line art
# BiRefNet fine-tune (egeorcun/lucida). FastAPI + web UI.
# Port: 8058
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

# Honest footprint — BiRefNet_HR fp32 @ 1024px. Re-measure after first real run.
TOOL_NAME="lucida"
REQ_VRAM_MIB=6000
REQ_RAM_MIB=6000
source scripts/vram_guard.sh

SERVICE_NAME="Lucida BG Remover"
PORT=8058
APP_DIR="$DRAGONSUITE_ROOT/projects/lucida"

service_header "$SERVICE_NAME" "$PORT"

if [ ! -d "$APP_DIR" ]; then
    echo "❌ Project not found: $APP_DIR"
    echo "   git clone https://github.com/egeorcun/lucida $APP_DIR"
    exit 1
fi
if [ ! -d "$HOME/.cache/huggingface/hub/models--egeorcun--lucida" ]; then
    echo "❌ Model not found — run: bash scripts/download_lucida_models.sh"
    exit 1
fi

vram_preflight || exit 1   # refuses if short; relaunch with CLEAR=1 to free registered tools
clear_port "$PORT"
activate_venv "projects/lucida/.venv"
set_pytorch_env

echo "🚀 Starting $SERVICE_NAME..."
if pgrep -f "uvicorn serving.app:app" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    cd "$APP_DIR"
    nohup python -m uvicorn serving.app:app --host 0.0.0.0 --port "$PORT" > /tmp/lucida.log 2>&1 &
    register_tool $!
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 120; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
        echo "   Model loads lazily on the first request (a few extra seconds)."
    else
        echo "❌ Not up in time — check /tmp/lucida.log"
        tail -15 /tmp/lucida.log
        exit 1
    fi
fi
