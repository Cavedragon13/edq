#!/bin/bash
# OmniVoice Studio - FastAPI backend + React frontend
# Cinematic dubbing: transcribe → translate → re-voice → mux
# Port 8051, LAN accessible
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="OmniVoice Studio"
PORT=8051
VENV="venv_omnivoice"
VENV_DIR="$DRAGONSUITE_ROOT/$VENV"
PROJECT_DIR="$DRAGONSUITE_ROOT/projects/omnivoice-studio"
LOG_FILE="/tmp/omnivoice.log"
OUTPUT_DIR="$HOME/ai_generated/omnivoice"

service_header "$SERVICE_NAME" "$PORT"
gpu_preflight "$PORT"

echo "🐍 Activating venv..."
source "$VENV_DIR/bin/activate" || { echo "❌ Failed to activate venv"; exit 1; }

mkdir -p "$OUTPUT_DIR"

export HF_HUB_DISABLE_TELEMETRY=1
export OMNIVOICE_OUTPUT_DIR="$OUTPUT_DIR"

echo "🚀 Starting $SERVICE_NAME..."
if pgrep -f "uvicorn backend.main:app.*--port $PORT" >/dev/null 2>&1; then
    echo "✓ Already running on port $PORT"
else
    cd "$PROJECT_DIR"
    nohup uvicorn backend.main:app --host 0.0.0.0 --port "$PORT" > "$LOG_FILE" 2>&1 &
    echo "⏳ Waiting for service and model load (420 sec timeout)..."
    if wait_for_port "$PORT" 420; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Service did not start in time — check $LOG_FILE"
        tail -40 "$LOG_FILE" || true
        exit 1
    fi
fi
