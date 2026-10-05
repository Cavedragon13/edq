#!/bin/bash
# Open Dots workspace. Web: 8007; API: loopback 8048.
set -euo pipefail

cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

PROJECT=/srv/containers/edq/projects/open-dots
VENV=/srv/containers/edq/venv_open_dots
DATA=/home/edq/.open-dots
LOG_DIR=/srv/containers/edq/logs/open-dots
WEB_PORT=8007
API_PORT=8048

service_header "Open Dots" "$WEB_PORT"

test -f "$PROJECT/server/run.py" || { echo "Open Dots source is missing"; exit 1; }
test -x "$VENV/bin/python" || { echo "Open Dots Python environment is missing"; exit 1; }
test -x "$PROJECT/client/node_modules/.bin/next" || { echo "Open Dots web dependencies are missing"; exit 1; }
test -d "$PROJECT/client/.next" || { echo "Open Dots web build is missing"; exit 1; }
curl -fsS --max-time 3 http://127.0.0.1:11434/api/version >/dev/null || { echo "Ollama is unavailable"; exit 1; }
docker image inspect open-dots-computer:1.62.1 >/dev/null 2>&1 || { echo "Open Dots computer image is missing"; exit 1; }

mkdir -p "$DATA/workspace" "$LOG_DIR"
chmod 700 "$DATA" "$DATA/workspace"

if curl -fsS --max-time 3 "http://127.0.0.1:$WEB_PORT/" >/dev/null 2>&1 && \
   curl -fsS --max-time 3 "http://127.0.0.1:$API_PORT/api/v1/health" >/dev/null 2>&1; then
    echo "Open Dots is already running"
    exit 0
fi

if ss -tln | grep -q ":$WEB_PORT "; then
    echo "Web port $WEB_PORT is occupied"
    exit 1
fi
if ss -tln | grep -q ":$API_PORT "; then
    echo "API port $API_PORT is occupied"
    exit 1
fi

export MODEL_API_KEY=ollama
export MODEL_API_BASE_URL=http://127.0.0.1:11434/v1
export DEFAULT_MODEL=gemma4:12b
export COMPUTER_PROVIDER=docker
export COMPUTER_DOCKER_IMAGE=open-dots-computer:1.62.1
export DATA_DIR="$DATA"
export WORKSPACE_ROOT="$DATA/workspace"
export HOST=127.0.0.1
export PORT="$API_PORT"
export CORS_ORIGINS="http://192.168.7.226:$WEB_PORT,http://127.0.0.1:$WEB_PORT,http://localhost:$WEB_PORT"

cd "$PROJECT/server"
nohup "$VENV/bin/python" "$PROJECT/server/run.py" > "$LOG_DIR/api.log" 2>&1 < /dev/null &
echo $! > "$LOG_DIR/api.pid"
if ! wait_for_port "$API_PORT" 45; then
    echo "Open Dots API failed; see $LOG_DIR/api.log"
    bash /srv/containers/edq/scripts/stop_open_dots.sh
    exit 1
fi

cd "$PROJECT/client"
nohup "$PROJECT/client/node_modules/.bin/next" start -p "$WEB_PORT" -H 0.0.0.0 > "$LOG_DIR/web.log" 2>&1 < /dev/null &
echo $! > "$LOG_DIR/web.pid"
if ! wait_for_port "$WEB_PORT" 60; then
    echo "Open Dots web app failed; see $LOG_DIR/web.log"
    bash /srv/containers/edq/scripts/stop_open_dots.sh
    exit 1
fi

echo "Open Dots ready at http://192.168.7.226:$WEB_PORT"
