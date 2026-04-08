#!/bin/bash
# Dungeon Generator - Browser-based D&D character generator
# Port: 8034
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="Dungeon Generator"
PORT=8034

service_header "$SERVICE_NAME" "$PORT"
clear_port "$PORT"

echo "🚀 Starting $SERVICE_NAME..."

if pgrep -f "http.server $PORT" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup python3 -m http.server "$PORT" --bind 0.0.0.0 --directory "$DRAGONSUITE_ROOT/projects/dnd-generator" > /tmp/dnd_generator.log 2>&1 &
    if wait_for_port "$PORT" 10; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Service did not start in time — check /tmp/dnd_generator.log"
        tail -5 /tmp/dnd_generator.log
        exit 1
    fi
fi
