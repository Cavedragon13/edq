#!/bin/bash
# YuE2 — full-song music generation with editable scores (m-a-p/YuE2-3B)
# Port: 8064
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

# Honest footprint. Upstream measured 11.2 GiB typical / 14.1 GiB max-context
# peak (BF16, no quantization) and asks for ~24 GB host RAM headroom.
TOOL_NAME="yue2"
REQ_VRAM_MIB=14500
REQ_RAM_MIB=16000
source scripts/vram_guard.sh

SERVICE_NAME="YuE2"
PORT=8064
VENV="venv_yue2"
SCRIPT="/srv/containers/edq/scripts/yue2_gradio.py"
LOG_FILE="/tmp/yue2.log"
HUB="${HF_HUB_CACHE:-$HOME/.cache/huggingface/hub}"

service_header "$SERVICE_NAME" "$PORT"

# Fail fast on missing weights — never download at launch.
if [ ! -d "$HUB/models--m-a-p--YuE2-3B/snapshots" ] || [ ! -d "$HUB/models--m-a-p--YuE2-Vae/snapshots" ]; then
    echo "❌ YuE2 weights not in the HF cache — run: bash scripts/download_yue2_models.sh"
    exit 1
fi

vram_preflight || exit 1
clear_port "$PORT"
activate_venv "$VENV"
set_pytorch_env

mkdir -p "$HOME/ai_generated/yue2"

echo "🚀 Starting $SERVICE_NAME..."
if pgrep -f "yue2_gradio[.]py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup python "$SCRIPT" > "$LOG_FILE" 2>&1 &
    register_tool $!
    echo "⏳ Waiting for service (model load ~1-2 min, log: $LOG_FILE)..."
    if wait_for_port "$PORT" 240; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Service did not start in time — check $LOG_FILE"
        tail -15 "$LOG_FILE"
        exit 1
    fi
fi
