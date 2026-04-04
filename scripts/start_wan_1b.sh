#!/bin/bash
# Wan2.1-T2V-1.3B — lightweight T2V model
# Port: 8016
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="Wan2.1-T2V-1.3B"
PORT=8016
VENV="venv_wan_1b"
SCRIPT="scripts/wan_1b_gradio.py"
MODEL_DIR="models/wan_1b"

service_header "$SERVICE_NAME" "$PORT"

if [ ! -d "$MODEL_DIR/transformer" ]; then
    echo "❌ Wan2.1-T2V-1.3B models not found at: $MODEL_DIR"
    echo ""
    echo "   Run the download script first:"
    echo "   bash scripts/download_wan_1b_models.sh"
    echo ""
    exit 1
fi

gpu_preflight "$PORT"
activate_venv "$VENV"
set_pytorch_env

echo "🚀 Starting $SERVICE_NAME..."

if pgrep -f "wan_1b_gradio.py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup python "$SCRIPT" > /tmp/wan_1b.log 2>&1 &
    echo "⏳ Waiting for service to start..."
    if wait_for_port "$PORT" 60; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Service did not start in time — check /tmp/wan_1b.log"
        tail -10 /tmp/wan_1b.log
        exit 1
    fi
fi
