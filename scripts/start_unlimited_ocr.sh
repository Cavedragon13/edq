#!/bin/bash
# Unlimited OCR 2 Studio — images/PDFs to Markdown with baidu/Unlimited-OCR-2 (Gradio)
# Port: 8007 (free slot in the Dragonsuite 8000-8099 range at install, 2026-11-06)
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

# Footprint: 3.3B bf16 (6.2GiB weights) resident on the GPU, plus activations per job.
# Measured 2026-11-06: card peak 7.86GB over a 612MiB baseline (~7.25GB for this service) on both a
# 2-page PDF (document mode) and a tiled single page; server RSS ~2.4GB. Long documents keep memory
# roughly flat (SR-SWA), but re-measure with a 50+ page PDF before trusting it there.
TOOL_NAME="unlimited-ocr"
REQ_VRAM_MIB=8000
REQ_RAM_MIB=4000
source scripts/vram_guard.sh

SERVICE_NAME="Unlimited OCR 2 Studio"
PORT=8007
VENV="venv_unlimited_ocr"
MODEL_DIR="$DRAGONSUITE_ROOT/models/unlimited-ocr-2"
OUT_DIR="/home/edq/ai_generated/unlimited-ocr"
SERVER="$DRAGONSUITE_ROOT/scripts/unlimited_ocr_app.py"
LOG="/srv/containers/edq/logs/unlimited_ocr_server.log"

service_header "$SERVICE_NAME" "$PORT"

if [ ! -f "$MODEL_DIR/model-00002-of-00002.safetensors" ] || [ ! -f "$MODEL_DIR/modeling_unlimitedocr.py" ]; then
    echo "❌ Model not found — run: bash scripts/download_unlimited_ocr_models.sh"
    exit 1
fi

if curl -s --max-time 2 "http://127.0.0.1:$PORT" > /dev/null 2>&1; then
    echo "✓ Already running on port $PORT"
    exit 0
fi

vram_preflight || exit 1   # refuses if short; relaunch with CLEAR=1 to free registered tools
clear_port "$PORT"
activate_venv "$VENV"
set_pytorch_env
mkdir -p "$OUT_DIR" "$(dirname "$LOG")"
export HF_HUB_OFFLINE=1

echo "🚀 Starting $SERVICE_NAME..."
setsid nohup "$DRAGONSUITE_ROOT/$VENV/bin/python" "$SERVER" < /dev/null > "$LOG" 2>&1 &
register_tool $!
echo "⏳ Waiting for service..."
if wait_for_port "$PORT" 120; then
    echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT  (model loads in the background, ~20s)"
else
    echo "❌ Not up in time — check $LOG"
    tail -30 "$LOG"
    exit 1
fi
