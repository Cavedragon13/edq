#!/bin/bash
# LivePortrait — Portrait Animation
# Port: 8006
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

# Honest footprint (vram_guard). Measured during a real generation (s9.jpg +
# d0.mp4 driving video, default sliders) 2026-10-18: peak 2623MiB total used
# vs ~930MiB desktop baseline -> ~1693MiB; steady-state RSS ~2707MiB.
TOOL_NAME="liveportrait"
REQ_VRAM_MIB=1800           # measured peak ~1693MiB above desktop baseline, 2026-10-18
REQ_RAM_MIB=2900            # measured steady-state RSS ~2707MiB, 2026-10-18
source scripts/vram_guard.sh

SERVICE_NAME="LivePortrait"
PORT=8006
VENV="venv_liveportrait"
APP_DIR="$DRAGONSUITE_ROOT/projects/LivePortrait"
OUTPUT_DIR="$HOME/ai_generated/liveportrait"

service_header "$SERVICE_NAME" "$PORT"
vram_preflight || exit 1   # refuses if VRAM/RAM short; relaunch with CLEAR=1 to stop other registered tools first
clear_port "$PORT"
activate_venv "$VENV"
set_pytorch_env

mkdir -p "$OUTPUT_DIR"
export LIVEPORTRAIT_OUTPUT_DIR="$OUTPUT_DIR"

echo "🚀 Starting $SERVICE_NAME..."
if pgrep -f "LivePortrait.*app.py\|liveportrait.*app.py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup bash -c "cd '$APP_DIR' && exec python app.py --server-port $PORT --server-name 0.0.0.0" > /tmp/liveportrait.log 2>&1 &
    LP_WRAPPER_PID=$!
    echo "⏳ Waiting for service..."
    register_tool "$LP_WRAPPER_PID"
    if wait_for_port "$PORT" 60; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Service did not start in time — check /tmp/liveportrait.log"
        tail -10 /tmp/liveportrait.log
        exit 1
    fi
fi
