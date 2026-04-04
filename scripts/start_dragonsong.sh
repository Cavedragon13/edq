#!/bin/bash
# Dragonsong - Lyria RealTime Music
# Port: 8029
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="Dragonsong"
PORT=8029
VENV="venv_dragonsong"

service_header "$SERVICE_NAME" "$PORT"
clear_port "$PORT"
activate_venv "$VENV"

echo "🚀 Starting $SERVICE_NAME..."

if pgrep -f "dragonsong_server.py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup python scripts/dragonsong_server.py > /tmp/dragonsong.log 2>&1 &
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 30; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Service did not start in time — check /tmp/dragonsong.log"
        tail -10 /tmp/dragonsong.log
        exit 1
    fi
fi
