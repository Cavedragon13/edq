#!/bin/bash
# Mercury2 Diffusion Chat — Start Script
# Port: 8036  |  No GPU venv  |  Requires MERCURY2_API_KEY
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="Mercury2 Diffusion Chat"
PORT=8036

service_header "$SERVICE_NAME" "$PORT"
clear_port "$PORT"

# Check API key
source /srv/containers/edq/.env 2>/dev/null || true
if [ -z "$MERCURY2_API_KEY" ]; then
    echo "❌ MERCURY2_API_KEY not found in /srv/containers/edq/.env"
    exit 1
fi
echo "✓ Mercury2 API key found"

echo "🚀 Starting $SERVICE_NAME..."
if pgrep -f "mercury2_server.py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup /usr/bin/python3 scripts/mercury2_server.py > /tmp/mercury2_server.log 2>&1 &
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 30; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
        echo "   Model: mercury-2 (Inception Labs)"
        echo "   Feature: Diffusion streaming — watch tokens crystallize"
    else
        echo "❌ Service did not start in time — check /tmp/mercury2_server.log"
        tail -10 /tmp/mercury2_server.log
        exit 1
    fi
fi
