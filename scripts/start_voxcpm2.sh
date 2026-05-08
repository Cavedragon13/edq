#!/bin/bash
# VoxCPM2 TTS — 2B diffusion, 48kHz, 30+ languages, voice design & cloning
# Port: 8049
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="VoxCPM2 TTS"
PORT=8049
VENV="venv_voxcpm2"
LOG="/tmp/voxcpm2.log"

export HF_HOME=/srv/containers/edq/cache_huggingface

service_header "$SERVICE_NAME" "$PORT"

if [ ! -d "$HF_HOME/hub/models--openbmb--VoxCPM2" ]; then
    echo "❌ VoxCPM2 model not found in HF cache."
    echo "   Run: bash scripts/download_voxcpm2_models.sh"
    exit 1
fi

gpu_preflight "$PORT"
activate_venv "$VENV"
set_pytorch_env

echo "🚀 Starting $SERVICE_NAME..."
if ss -tlnp | grep -q ":${PORT} "; then
    echo "✓ Already running on port $PORT"
else
    nohup python3 scripts/voxcpm2_server.py > "$LOG" 2>&1 &
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 120; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Service did not start — check $LOG"
        tail -10 "$LOG"
        exit 1
    fi
fi
