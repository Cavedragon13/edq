#!/bin/bash
# CoverSynth OpenAI - playlist analysis and cover generation
# Port: 8053
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh
SERVICE_NAME="CoverSynth OpenAI"
PORT=8053
PROJECT_DIR="$DRAGONSUITE_ROOT/projects/coversynth-openai"
SERVER="$PROJECT_DIR/server.py"
service_header "$SERVICE_NAME" "$PORT"
clear_port "$PORT"
if [ ! -f "$SERVER" ]; then echo "ERROR: server.py not found at $SERVER"; exit 1; fi
if ! grep -q "^OPENAI_API_KEY=" /srv/containers/edq/.env 2>/dev/null; then echo "NOTE: OPENAI_API_KEY not found - OpenAI calls will fail."; fi
nohup env PORT="$PORT" "$DRAGONSUITE_ROOT/venv_dragonsuite/bin/python" "$SERVER" > /tmp/coversynth_openai.log 2>&1 &
if wait_for_port "$PORT" 10; then echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"; else echo "❌ Service did not start in time — check /tmp/coversynth_openai.log"; tail -20 /tmp/coversynth_openai.log; exit 1; fi
