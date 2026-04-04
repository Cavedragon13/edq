#!/bin/bash
# HeartMuLa Music Generator - Open Source Music Foundation Model
# Port: 8004
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="HeartMuLa"
PORT=8004
VENV="venv_heartmula"
HEARTMULA_DIR="$DRAGONSUITE_ROOT/projects/heartmula"
MODEL_DIR="$HEARTMULA_DIR/ckpt"

service_header "$SERVICE_NAME" "$PORT"
gpu_preflight "$PORT"
activate_venv "$VENV"
set_pytorch_env

export HEARTMULA_MODEL_DIR="$MODEL_DIR"
export GRADIO_SERVER_NAME="0.0.0.0"
export GRADIO_SERVER_PORT="$PORT"

echo "🚀 Starting $SERVICE_NAME..."
mkdir -p "$HOME/ai_generated/heartmula"

if pgrep -f "app_local.py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    cd "$HEARTMULA_DIR"
    nohup python app_local.py > /tmp/heartmula.log 2>&1 &
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 30; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Service did not start in time — check /tmp/heartmula.log"
        tail -10 /tmp/heartmula.log
        exit 1
    fi
fi
