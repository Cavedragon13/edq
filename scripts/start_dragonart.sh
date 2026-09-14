#!/bin/bash
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh
TOOL_NAME="dragonart-studio"
REQ_VRAM_MIB=0
REQ_RAM_MIB=512
source scripts/vram_guard.sh
SERVICE_NAME="dragonart-studio"
PORT=8015
service_header "$SERVICE_NAME" "$PORT"
PYTHON_BIN="$DRAGONSUITE_ROOT/venv_dragonsuite/bin/python"
"$PYTHON_BIN" -c 'import openai; from google import genai; import dotenv; import cv2; from PIL import Image'
export NVM_DIR="/home/edq/.nvm"
source "$NVM_DIR/nvm.sh"
nvm use 20 --silent
cd "$DRAGONSUITE_ROOT/projects/dragonart-studio"
npm run build
cd "$DRAGONSUITE_ROOT"
mkdir -p "$DRAGONSUITE_ROOT/logs/dragonart-studio" "/home/edq/ai_generated/dragonart-studio"
vram_preflight || exit 1
clear_port "$PORT"
nohup "$PYTHON_BIN" "$DRAGONSUITE_ROOT/scripts/dragonart_server.py" > "$DRAGONSUITE_ROOT/logs/dragonart-studio/server.log" 2>&1 &
register_tool $!
if wait_for_port "$PORT" 30; then
    echo "Ready: http://192.168.7.226:$PORT"
else
    tail -20 "$DRAGONSUITE_ROOT/logs/dragonart-studio/server.log"
    exit 1
fi
