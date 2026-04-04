#!/bin/bash
# GPU Monitor — Minimal floating GPU stats display
# Port: 8015
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="GPU Monitor"
PORT=8015
SCRIPT="scripts/gpu_monitor_server.py"

service_header "$SERVICE_NAME" "$PORT"
clear_port "$PORT"

echo "🚀 Starting $SERVICE_NAME..."

if pgrep -f "gpu_monitor_server.py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup python3 "$SCRIPT" > /tmp/gpu_monitor.log 2>&1 &
    if wait_for_port "$PORT" 15; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Failed — check /tmp/gpu_monitor.log"
        tail -10 /tmp/gpu_monitor.log
        exit 1
    fi
fi
