#!/bin/bash
# Foundation-1 — Music Generation Model
# Port: 8027  |  GPU  |  venv_foundation1
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="Foundation-1"
PORT=8027
VENV="venv_foundation1"
PROJECT_DIR="/srv/containers/edq/projects/foundation-1"
MODEL="$PROJECT_DIR/models/Foundation_1.safetensors"
CONFIG="$PROJECT_DIR/models/model_config.json"
OUTPUT_DIR="$HOME/ai_generated/foundation-1"

service_header "$SERVICE_NAME" "$PORT"

if [ ! -f "$MODEL" ]; then
    echo "❌ Foundation-1 model not found: $MODEL"
    echo "   Run: bash scripts/download_foundation1_models.sh"
    exit 1
fi

gpu_preflight "$PORT"
activate_venv "$VENV"
set_pytorch_env

export GRADIO_SERVER_PORT=$PORT
export GRADIO_SERVER_NAME="0.0.0.0"

mkdir -p "$OUTPUT_DIR"

echo "🚀 Starting $SERVICE_NAME..."
if pgrep -f "$PROJECT_DIR/run_gradio.py" > /dev/null && ss -ltn "( sport = :$PORT )" | grep -q LISTEN; then
    echo "✓ Already running on port $PORT"
else
    cd "$PROJECT_DIR"
    nohup python run_gradio.py \
        --model-config "$CONFIG" \
        --ckpt-path "$MODEL" \
        --model-half \
        --title "Foundation-1" > /tmp/foundation1.log 2>&1 &
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 60; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Service did not start in time — check /tmp/foundation1.log"
        tail -10 /tmp/foundation1.log
        exit 1
    fi
fi
