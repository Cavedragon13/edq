#!/bin/bash
# Rembg — AI background removal
# Port: 8012
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="Rembg"
PORT=8012
VENV="venv_rembg"
SCRIPT="scripts/rembg_server.py"

service_header "$SERVICE_NAME" "$PORT"
gpu_preflight "$PORT"
activate_venv "$VENV"
export NUMBA_CACHE_DIR="/tmp/numba-rembg"
mkdir -p "$NUMBA_CACHE_DIR"
python -c "import fastapi, uvicorn, multipart, rembg" >/dev/null 2>&1 || {
    echo "❌ Missing Rembg server dependencies in $VENV"
    echo "   Run setup/install outside launch; do not download dependencies during creative startup."
    exit 1
}
set_pytorch_env

mkdir -p "$HOME/ai_generated/rembg"
echo "🚀 Starting $SERVICE_NAME..."

if pgrep -f "rembg_server.py" > /dev/null; then
    if curl -s --max-time 2 "http://127.0.0.1:$PORT/" > /dev/null 2>&1; then
        echo "✓ Already running on port $PORT"
    else
        echo "⚠️  Found stale Rembg process without a listening port; stopping it..."
        pkill -f "rembg_server.py" || true
        sleep 2
        nohup python "$SCRIPT" > /tmp/rembg.log 2>&1 &
        echo "⏳ Waiting for service..."
        if wait_for_port "$PORT" 30; then
            echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
        else
            echo "❌ Service did not start in time — check /tmp/rembg.log"
            tail -10 /tmp/rembg.log
            exit 1
        fi
    fi
else
    nohup python "$SCRIPT" > /tmp/rembg.log 2>&1 &
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 30; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Service did not start in time — check /tmp/rembg.log"
        tail -10 /tmp/rembg.log
        exit 1
    fi
fi
