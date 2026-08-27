#!/bin/bash
# DRIVE ARCHAEOLOGY — web UI for imaging old drives with ddrescue
# Port: 8061
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

TOOL_NAME="drivearchaeology"
REQ_VRAM_MIB=0      # no GPU use
REQ_RAM_MIB=300      # small FastAPI process
source scripts/vram_guard.sh

SERVICE_NAME="Drive Archaeology"
PORT=8061
VENV="venv_drivearchaeology"
APP_DIR="/srv/containers/edq/drive-archaeology"

service_header "$SERVICE_NAME" "$PORT"

if [ ! -f "$APP_DIR/server.py" ]; then
    echo "❌ App not found: $APP_DIR/server.py"
    exit 1
fi
if [ ! -f /etc/sudoers.d/drivearchaeology ]; then
    echo "❌ Missing sudoers rule for image_drive.sh — imaging runs will fail."
    echo "   See /etc/sudoers.d/drivearchaeology"
    exit 1
fi

vram_preflight || exit 1
clear_port "$PORT"
activate_venv "$VENV"

echo "🚀 Starting $SERVICE_NAME..."
if pgrep -f "uvicorn server:app.*--port $PORT" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    cd "$APP_DIR"
    nohup /srv/containers/edq/venv_drivearchaeology/bin/uvicorn server:app --host 0.0.0.0 --port "$PORT" \
        > /tmp/drivearchaeology.log 2>&1 &
    register_tool $!
    cd /srv/containers/edq
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 30; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Not up in time — check /tmp/drivearchaeology.log"
        tail -15 /tmp/drivearchaeology.log
        exit 1
    fi
fi
