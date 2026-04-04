#!/bin/bash
# JustDubit — video dubbing / lip-sync service
# Port: 8022
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="JustDubit"
PORT=8022
SCRIPT="scripts/justdubit_gradio.py"

service_header "$SERVICE_NAME" "$PORT"
gpu_preflight "$PORT"
set_pytorch_env

echo "⚠️  JustDubit requires ~50GB of model checkpoints."
echo "   Set checkpoint paths in $SCRIPT before use."
echo ""
echo "🚀 Starting $SERVICE_NAME..."

if pgrep -f "justdubit_gradio.py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup python "$SCRIPT" > /tmp/justdubit.log 2>&1 &
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 60; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Failed — check /tmp/justdubit.log"
        tail -10 /tmp/justdubit.log
        exit 1
    fi
fi
