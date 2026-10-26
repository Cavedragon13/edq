#!/bin/bash
# Qwen-Image 2.1 Studio — text-to-image, multi-reference editing, transparent RGBA (Gradio)
# Port: 8076 (next free port in the Dragonsuite 8000-8099 home range at install, 2026-10-25)
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

# Footprint: NF4 DiT + NF4 Qwen3-VL encoder with model CPU offload (scripts/qwen_image_21_gradio.py).
# Measured 2026-10-25: peak 7.7GB card VRAM for t2i at any size (incl. 2752x1536), 9.2GB for edits;
# idle ~0.35GB after each job; server RSS ~14GB. The app re-checks VRAM per request and refuses cleanly.
TOOL_NAME="qwen-image-21"
REQ_VRAM_MIB=9000
REQ_RAM_MIB=15000
source scripts/vram_guard.sh

SERVICE_NAME="Qwen-Image 2.1 Studio"
PORT=8076
VENV="venv_qwen_image_21"
MODEL_ROOT="$DRAGONSUITE_ROOT/models/qwen-image-21"
OUT_DIR="/home/edq/ai_generated/qwen-image-21"
SERVER="$DRAGONSUITE_ROOT/scripts/qwen_image_21_gradio.py"
LOG="/srv/containers/edq/logs/qwen_image_21_server.log"

service_header "$SERVICE_NAME" "$PORT"

if [ ! -f "$MODEL_ROOT/Qwen-Image-2.1/model_index.json" ] || [ ! -f "$MODEL_ROOT/Qwen-Image-2.1-Turbo/model_index.json" ]; then
    echo "❌ Models not found — run: bash scripts/download_qwen_image_21_models.sh"
    exit 1
fi
if [ ! -f "$MODEL_ROOT/nf4/transformer-turbo/config.json" ] || [ ! -f "$MODEL_ROOT/nf4/text_encoder/config.json" ]; then
    echo "❌ NF4 weights not built — run: venv_qwen_image_21/bin/python scripts/quantize_qwen_image_21.py"
    exit 1
fi

if curl -s --max-time 2 "http://127.0.0.1:$PORT" > /dev/null 2>&1; then
    echo "✓ Already running on port $PORT"
    exit 0
fi

vram_preflight || exit 1   # refuses if short; never touches Ollama/Gemma or unregistered processes
clear_port "$PORT"
activate_venv "$VENV"
set_pytorch_env
mkdir -p "$OUT_DIR" "$(dirname "$LOG")"
export HF_HUB_OFFLINE=1

echo "🚀 Starting $SERVICE_NAME..."
setsid nohup "$DRAGONSUITE_ROOT/$VENV/bin/python" "$SERVER" < /dev/null > "$LOG" 2>&1 &
register_tool $!
echo "⏳ Waiting for service..."
if wait_for_port "$PORT" 180; then
    echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT  (model warms up in the background)"
else
    echo "❌ Not up in time — check $LOG"
    tail -30 "$LOG"
    exit 1
fi
