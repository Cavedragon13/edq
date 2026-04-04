#!/bin/bash
# M.U.L.E. - Planet Irata (tribute to Dani Bunten Berry)
# Port: 8032
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="M.U.L.E."
PORT=8032

service_header "$SERVICE_NAME" "$PORT"
clear_port "$PORT"

echo "🚀 Starting $SERVICE_NAME..."

if pgrep -f "http.server $PORT" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup python3 -m http.server "$PORT" --bind 0.0.0.0 --directory "$DRAGONSUITE_ROOT/media" > /tmp/mule_game.log 2>&1 &
    if wait_for_port "$PORT" 10; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT/mule_game.html"
    else
        echo "❌ Service did not start in time — check /tmp/mule_game.log"
        tail -5 /tmp/mule_game.log
        exit 1
    fi
fi
