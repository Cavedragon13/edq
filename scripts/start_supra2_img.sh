#!/bin/bash
# Supra2-IMG — compact 256px text-to-image service
# Port: 8070
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

TOOL_NAME="supra2-img"
REQ_VRAM_MIB=6000
REQ_RAM_MIB=6000
source scripts/vram_guard.sh

SERVICE_NAME="Supra2-IMG"
PORT=8070
VENV="venv_supra2_img"
CHECKPOINT="$DRAGONSUITE_ROOT/models/supra2-img/model_final_ema.pt"
APP="$DRAGONSUITE_ROOT/projects/Supra2-IMG"

service_header "$SERVICE_NAME" "$PORT"
if [ ! -f "$APP/inference.py" ]; then
    echo "❌ Project not found: $APP"
    exit 1
fi
if [ ! -f "$CHECKPOINT" ] || [ ! -f "$DRAGONSUITE_ROOT/models/supra2-img/flan-t5-base/config.json" ] || [ ! -f "$DRAGONSUITE_ROOT/models/supra2-img/sd-vae-ft-mse/config.json" ]; then
    echo "❌ Models not ready — run: bash scripts/download_supra2_img_models.sh"
    exit 1
fi

vram_preflight || exit 1
clear_port "$PORT"
activate_venv "$VENV"
set_pytorch_env
export DRAGONSUITE_SCRIPTS="$DRAGONSUITE_ROOT/scripts"
mkdir -p /home/edq/ai_generated/supra2-img

echo "🚀 Starting $SERVICE_NAME..."
if pgrep -f "[s]upra2_server.py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    setsid nohup python "$DRAGONSUITE_ROOT/scripts/supra2_server.py" < /dev/null > /tmp/supra2_img.log 2>&1 &
    register_tool $!
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 60; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Not up in time — check /tmp/supra2_img.log"
        tail -30 /tmp/supra2_img.log
        exit 1
    fi
fi
