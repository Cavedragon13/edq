#!/bin/bash
# Topaz Labs AI Enhancement — Cloud image enhancement via Topaz API
# Port: 8019
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="Topaz Labs"
PORT=8019
VENV="venv_topaz_gradio"
SCRIPT="scripts/topaz_labs_gradio.py"

service_header "$SERVICE_NAME" "$PORT"

# Check for API key before doing anything else
if ! grep -q "TOPAZ_API_KEY" "$DRAGONSUITE_ROOT/.env" 2>/dev/null; then
    echo "❌ TOPAZ_API_KEY not found in .env"
    echo "   Get your API key from: https://developer.topazlabs.com/"
    exit 1
fi

clear_port "$PORT"
activate_venv "$VENV"

echo "🚀 Starting $SERVICE_NAME..."

if pgrep -f "topaz_labs_gradio.py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup python "$SCRIPT" > /tmp/topaz_labs.log 2>&1 &
    if wait_for_port "$PORT" 30; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Failed — check /tmp/topaz_labs.log"
        tail -10 /tmp/topaz_labs.log
        exit 1
    fi
fi
