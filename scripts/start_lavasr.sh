#!/bin/bash
# LavaSR Speech Enhancement
# Port: 8034
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="LavaSR"
PORT=8034
VENV="venv_lavasr"
SCRIPT="scripts/lavasr_server.py"
MODEL_CACHE="$HOME/.cache/huggingface/hub/models--YatharthS--LavaSR"

service_header "$SERVICE_NAME" "$PORT"

# Check model downloaded
if [ ! -d "$MODEL_CACHE" ]; then
    echo "❌ LavaSR models not found at: $MODEL_CACHE"
    echo ""
    echo "   Run the download script first:"
    echo "   bash scripts/download_lavasr_models.sh"
    echo ""
    exit 1
fi

gpu_preflight "$PORT"
activate_venv "$VENV"
set_pytorch_env

echo "🚀 Starting $SERVICE_NAME..."
if pgrep -f "lavasr_server.py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup python3 "$SCRIPT" > /tmp/lavasr.log 2>&1 &
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 30; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Service did not start in time — check /tmp/lavasr.log"
        tail -10 /tmp/lavasr.log
        exit 1
    fi
fi
