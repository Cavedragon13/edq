#!/bin/bash
# SoulX-Singer
# Port: 8023
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="SoulX-Singer"
PORT=8023
VENV="venv_soulxsinger"

service_header "$SERVICE_NAME" "$PORT"
gpu_preflight "$PORT"
activate_venv "$VENV"
set_pytorch_env

echo "🚀 Starting $SERVICE_NAME..."
if pgrep -f "SoulX-Singer/webui.py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup bash -c 'cd /srv/containers/edq/projects/SoulX-Singer && python webui.py --port 8023' > /tmp/soulxsinger.log 2>&1 &
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 30; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Service did not start in time — check /tmp/soulxsinger.log"
        tail -10 /tmp/soulxsinger.log
        exit 1
    fi
fi
