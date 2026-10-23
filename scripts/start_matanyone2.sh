#!/bin/bash
# MatAnyone 2 — Human Video Matting (CVPR 2026)
# Port: 8038
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

TOOL_NAME="matanyone2"
REQ_VRAM_MIB=7200          # measured peak ~6.86GB (image matting smoke test), 2026-10-23
REQ_RAM_MIB=3500           # measured RSS ~2.4GB, 2026-10-23
source scripts/vram_guard.sh

SERVICE_NAME="MatAnyone 2"
PORT=8038
VENV="venv_matanyone2"
APP_DIR="$DRAGONSUITE_ROOT/projects/matanyone2/hugging_face"
CHECKPOINTS_DIR="$DRAGONSUITE_ROOT/projects/matanyone2/pretrained_models"
OUTPUT_DIR="$HOME/ai_generated/matanyone2"

service_header "$SERVICE_NAME" "$PORT"

# Project and model checks before GPU preflight
if [ ! -d "$APP_DIR" ]; then
    echo "❌ MatAnyone2 project not found at: $APP_DIR"
    echo "   git clone https://github.com/pq-yang/MatAnyone2 projects/matanyone2"
    exit 1
fi

if [ ! -f "$CHECKPOINTS_DIR/sam_vit_h_4b8939.pth" ] || [ ! -f "$CHECKPOINTS_DIR/matanyone2.pth" ]; then
    echo "❌ Model files not found at: $CHECKPOINTS_DIR"
    echo "   Run: bash scripts/download_matanyone2_models.sh"
    exit 1
fi

vram_preflight || exit 1   # refuses if VRAM/RAM short; relaunch with CLEAR=1 to stop other registered tools first
clear_port "$PORT"
activate_venv "$VENV"
set_pytorch_env
mkdir -p "$OUTPUT_DIR"
export MATANYONE2_OUTPUT_DIR="$OUTPUT_DIR"

echo "🚀 Starting $SERVICE_NAME..."
if pgrep -f "matanyone2/hugging_face/app.py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup bash -c "cd '$APP_DIR' && python app.py --port $PORT" > /tmp/matanyone2.log 2>&1 &
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 60; then
        server_pid=$(ss -tlnp "sport = :$PORT" | grep -oP 'pid=\K[0-9]+' | head -1)
        [ -n "$server_pid" ] && register_tool "$server_pid"
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Service did not start in time — check /tmp/matanyone2.log"
        tail -10 /tmp/matanyone2.log
        exit 1
    fi
fi
