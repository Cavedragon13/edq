#!/bin/bash
# FrameForge - structured JSON image sequence prompting
# Port: 8054
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh
SERVICE_NAME="FrameForge"
PORT=8054
PROJECT_DIR="$DRAGONSUITE_ROOT/projects/coversynth-json"
SERVER="$PROJECT_DIR/server.py"
service_header "$SERVICE_NAME" "$PORT"
clear_port "$PORT"
if [ ! -f "$SERVER" ]; then echo "ERROR: server.py not found at $SERVER"; exit 1; fi
if ! grep -q "^OPENAI_API_KEY=" /srv/containers/edq/.env 2>/dev/null; then echo "NOTE: OPENAI_API_KEY not found - OpenAI calls will fail."; fi
nohup env PORT="$PORT" "$DRAGONSUITE_ROOT/venv_dragonsuite/bin/python" "$SERVER" > /tmp/coversynth_json.log 2>&1 &
if wait_for_port "$PORT" 10; then echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"; else echo "❌ Service did not start in time — check /tmp/coversynth_json.log"; tail -20 /tmp/coversynth_json.log; exit 1; fi
