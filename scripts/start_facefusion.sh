#!/bin/bash
# FaceFusion — Face Swap & Manipulation
# Port: 8017
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="FaceFusion"
PORT=8017
VENV="venv_facefusion"

service_header "$SERVICE_NAME" "$PORT"
gpu_preflight "$PORT"
activate_venv "$VENV"
set_pytorch_env

export GRADIO_SERVER_NAME=0.0.0.0
export GRADIO_SERVER_PORT=$PORT

echo "🚀 Starting $SERVICE_NAME..."

if pgrep -f "facefusion.py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    cd /srv/containers/edq/projects/facefusion
    nohup python facefusion.py run \
        --execution-providers cuda \
        --ui-layouts webcam benchmark \
        > /tmp/facefusion.log 2>&1 &
    if wait_for_port "$PORT" 60; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Failed — check /tmp/facefusion.log"
        tail -10 /tmp/facefusion.log
        exit 1
    fi
fi
