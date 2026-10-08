#!/bin/bash
# Battle Cars — 3D post-apocalyptic car combat racer (Three.js, browser)
# Port: 8069. Static game + save API served by projects/battle-cars/server.py (stdlib only, no venv, no GPU).
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

TOOL_NAME="battle-cars"
REQ_VRAM_MIB=0
REQ_RAM_MIB=256
source scripts/vram_guard.sh

SERVICE_NAME="Battle Cars"
PORT=8069
PROJECT="$DRAGONSUITE_ROOT/projects/battle-cars"
LOG_DIR="$DRAGONSUITE_ROOT/logs/battle-cars"

service_header "$SERVICE_NAME" "$PORT"

if [ ! -f "$PROJECT/server.py" ] || [ ! -f "$PROJECT/vendor/three.module.js" ]; then
    echo "Battle Cars source is missing: $PROJECT"
    exit 1
fi

mkdir -p "$LOG_DIR" "/home/edq/ai_generated/battle-cars"

vram_preflight || exit 1
clear_port "$PORT"

echo "Starting $SERVICE_NAME..."
setsid nohup python3 "$PROJECT/server.py" "$PORT" > "$LOG_DIR/server.log" 2>&1 < /dev/null &
register_tool $!
if wait_for_port "$PORT" 20; then
    echo "$SERVICE_NAME ready at http://192.168.7.226:$PORT/"
else
    echo "Did not start in time; see $LOG_DIR/server.log"
    tail -15 "$LOG_DIR/server.log"
    exit 1
fi
