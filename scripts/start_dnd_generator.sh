#!/bin/bash
# RPG Char Gen - Browser-based RPG character generator
# Port: 8034
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="RPG Char Gen"
PORT=8034
PROJECT_DIR="$DRAGONSUITE_ROOT/projects/dnd-generator"
SERVER="$PROJECT_DIR/server.py"

service_header "$SERVICE_NAME" "$PORT"
clear_port "$PORT"

echo "🚀 Starting $SERVICE_NAME..."

if [ ! -f "$SERVER" ]; then
    echo "ERROR: server.py not found at $SERVER"
    exit 1
fi

if [ -f "/srv/containers/edq/.env" ]; then
    OPENAI_KEY=$(grep -E "^OPENAI_API_KEY=" /srv/containers/edq/.env | cut -d'=' -f2-)
    if [ -z "$OPENAI_KEY" ]; then
        echo "NOTE: OPENAI_API_KEY not found - AI portraits will not be available."
    fi
else
    echo "NOTE: /srv/containers/edq/.env not found - AI portraits will not be available."
fi

if pgrep -f "dnd-generator/server.py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup env PORT="$PORT" python3 "$SERVER" > /tmp/dnd_generator.log 2>&1 &
    if wait_for_port "$PORT" 10; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Service did not start in time — check /tmp/dnd_generator.log"
        tail -5 /tmp/dnd_generator.log
        exit 1
    fi
fi
