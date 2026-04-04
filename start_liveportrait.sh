#!/bin/bash
# LivePortrait — Portrait Animation
# Port: 8006
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="LivePortrait"
PORT=8006
VENV="venv_liveportrait"
APP_DIR="$DRAGONSUITE_ROOT/projects/LivePortrait"
OUTPUT_DIR="$HOME/ai_generated/liveportrait"

service_header "$SERVICE_NAME" "$PORT"
gpu_preflight "$PORT"
activate_venv "$VENV"
set_pytorch_env

mkdir -p "$OUTPUT_DIR"
export LIVEPORTRAIT_OUTPUT_DIR="$OUTPUT_DIR"

echo "🚀 Starting $SERVICE_NAME..."
if pgrep -f "LivePortrait.*app.py\|liveportrait.*app.py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup bash -c "cd '$APP_DIR' && python app.py --server-port $PORT --server-name 0.0.0.0" > /tmp/liveportrait.log 2>&1 &
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 60; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Service did not start in time — check /tmp/liveportrait.log"
        tail -10 /tmp/liveportrait.log
        exit 1
    fi
fi
