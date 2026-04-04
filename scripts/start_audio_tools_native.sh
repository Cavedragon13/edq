#!/bin/bash
# Audio Processing Suite - Native UI
# Port 8026, LAN accessible
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="Audio Processing Suite"
PORT=8026
VENV="venv_soulxsinger"

PREPROCESS_BASE="$DRAGONSUITE_ROOT/models/SoulX-Singer-Preprocess"

service_header "$SERVICE_NAME" "$PORT"

# Check model files before evicting GPU
if [ ! -d "$PREPROCESS_BASE/mel-band-roformer-karaoke" ]; then
    echo "❌ Audio processing models not found at: $PREPROCESS_BASE"
    echo ""
    echo "   Run the download script first:"
    echo "   bash scripts/download_soulxsinger_models.sh"
    echo ""
    exit 1
fi

gpu_preflight "$PORT"
activate_venv "$VENV"

# Install runtime dependencies if needed
pip install -q fastapi uvicorn python-multipart 2>/dev/null || true

set_pytorch_env

echo "🚀 Starting $SERVICE_NAME..."
if pgrep -f "audio_tools_server.py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup python scripts/audio_tools_server.py > /tmp/audio_tools.log 2>&1 &
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 60; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Service did not start in time — check /tmp/audio_tools.log"
        tail -10 /tmp/audio_tools.log
        exit 1
    fi
fi
