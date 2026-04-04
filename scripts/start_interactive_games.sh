#!/bin/bash
# Interactive Games - Survival Series, Lunar Reckoning, text adventures
# Port: 8031
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="Interactive Games"
PORT=8031

service_header "$SERVICE_NAME" "$PORT"
clear_port "$PORT"

echo "🚀 Starting $SERVICE_NAME..."

if pgrep -f "http.server $PORT" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup python3 -m http.server "$PORT" --bind 0.0.0.0 --directory "$DRAGONSUITE_ROOT/projects/interactive-games" > /tmp/interactive_games.log 2>&1 &
    if wait_for_port "$PORT" 10; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Service did not start in time — check /tmp/interactive_games.log"
        tail -5 /tmp/interactive_games.log
        exit 1
    fi
fi
