#!/bin/bash
# SenseNova-U1.5-8B-MoT — native unified multimodal T2I (Q8 GGUF + balanced layer-offload)
# Port: 8048
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

# Honest footprint — Q8 GGUF (19.9GB on disk) run with vram_mode=balanced and
# fast_vram_budget_gib=12 (see scripts/sensenova_server.py), so only a working
# set of layers is resident at once. 13500 keeps margin above the 12GB budget
# for activations; adjust after the first real generation is profiled.
TOOL_NAME="sensenova"
REQ_VRAM_MIB=13500
REQ_RAM_MIB=24000
source scripts/vram_guard.sh

SERVICE_NAME="SenseNova-U1.5-8B-MoT"
PORT=8048
VENV="venv_sensenova"
APP_DIR="$DRAGONSUITE_ROOT/projects/SenseNova-U1"
CONFIG_DIR="/srv/containers/edq/models/sensenova-u1.5"
GGUF_FILE="/srv/containers/edq/models/sensenova-u1.5/gguf/SenseNova-U1.5-8B-MoT-Preview-Q8.gguf"

service_header "$SERVICE_NAME" "$PORT"

if [ ! -d "$APP_DIR" ]; then
    echo "❌ Project not found: $APP_DIR"
    echo "   git clone --branch feat/u1.5 https://github.com/OpenSenseNova/SenseNova-U1.git projects/SenseNova-U1"
    exit 1
fi
if [ ! -f "$CONFIG_DIR/config.json" ] || [ ! -f "$GGUF_FILE" ]; then
    echo "❌ Model assets not found under $CONFIG_DIR"
    echo "   Run: bash scripts/download_sensenova_models.sh"
    exit 1
fi

vram_preflight || exit 1
clear_port "$PORT"
activate_venv "$VENV"
set_pytorch_env

echo "🚀 Starting $SERVICE_NAME..."
if pgrep -f "sensenova_server.py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup python scripts/sensenova_server.py --port "$PORT" > /tmp/sensenova.log 2>&1 &
    register_tool $!
    echo "⏳ Waiting for service (8B model load + GGUF dequant takes a while)..."
    if wait_for_port "$PORT" 300; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Not up in time — check /tmp/sensenova.log"
        tail -20 /tmp/sensenova.log
        exit 1
    fi
fi
