#!/bin/bash
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh
TOOL_NAME="coversynth-openai"
REQ_VRAM_MIB=0
REQ_RAM_MIB=512
source scripts/vram_guard.sh
SERVICE_NAME="coversynth-openai"
PORT=8053
service_header "$SERVICE_NAME" "$PORT"
PYTHON_BIN="$DRAGONSUITE_ROOT/venv_dragonsuite/bin/python"
"$PYTHON_BIN" -c 'import openai; from google import genai; import dotenv'
mkdir -p "$DRAGONSUITE_ROOT/logs/coversynth-openai" "/home/edq/ai_generated/coversynth-openai"
vram_preflight || exit 1
clear_port "$PORT"
nohup "$PYTHON_BIN" "$DRAGONSUITE_ROOT/projects/coversynth-openai/server.py" > "$DRAGONSUITE_ROOT/logs/coversynth-openai/server.log" 2>&1 &
register_tool $!
if wait_for_port "$PORT" 30; then
    echo "Ready: http://192.168.7.226:$PORT"
else
    tail -20 "$DRAGONSUITE_ROOT/logs/coversynth-openai/server.log"
    exit 1
fi
