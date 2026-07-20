#!/bin/bash
# MuScriptor — Multi-instrument music transcription, audio → MIDI (Kyutai, 1.4B)
# Piano-roll web UI + POST /transcribe SSE API
# Port: 8040
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

# Honest footprint — 1.4B transformer decoder. Estimate; re-measure once the
# gated weights are downloadable and adjust.
TOOL_NAME="muscriptor"
REQ_VRAM_MIB=7000
REQ_RAM_MIB=6000
source scripts/vram_guard.sh

SERVICE_NAME="MuScriptor"
PORT=8040
VENV="venv_muscriptor"

service_header "$SERVICE_NAME" "$PORT"

if [ ! -d "$HOME/.cache/huggingface/hub/models--MuScriptor--muscriptor-large" ]; then
    echo "❌ Model not found — run: bash scripts/download_muscriptor_models.sh"
    echo "   (Gated repo: accept terms first at https://huggingface.co/MuScriptor/muscriptor-large)"
    exit 1
fi

vram_preflight || exit 1   # refuses if short; relaunch with CLEAR=1 to free registered tools
clear_port "$PORT"
activate_venv "$VENV"
set_pytorch_env

echo "🚀 Starting $SERVICE_NAME..."
if pgrep -f "muscriptor_server.py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup python scripts/muscriptor_server.py --model large --port "$PORT" --host 0.0.0.0 \
        > /tmp/muscriptor.log 2>&1 &
    register_tool $!
    echo "⏳ Waiting for service (1.4B model load)..."
    if wait_for_port "$PORT" 180; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Not up in time — check /tmp/muscriptor.log"
        tail -15 /tmp/muscriptor.log
        exit 1
    fi
fi
