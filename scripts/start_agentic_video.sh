#!/bin/bash
# Agentic Video Editor - 4-Agent Video Ad Pipeline (Gradio Wrapper)
# Director → Trim Refiner → Editor → Reviewer agents
# Port 8044, LAN accessible
set -euo pipefail

cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="Agentic Video Editor"
PORT=8044
VENV="venv_agentic_video"
VENV_DIR="$DRAGONSUITE_ROOT/$VENV"
OUTPUT_DIR="$HOME/ai_generated/agentic_video"
LOG_FILE="/tmp/agentic_video.log"
APP_SCRIPT="$DRAGONSUITE_ROOT/scripts/agentic_video_gradio.py"

service_header "$SERVICE_NAME" "$PORT"

echo "🔧 Pre-flight checks..."
vram_status
pkill -f "agentic_video_gradio.py" 2>/dev/null || true
clear_port "$PORT"
echo "✓ VRAM status:"
vram_status
echo ""

if [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo "❌ Virtual environment not found: $VENV_DIR"
    exit 1
fi

activate_venv "$VENV"

mkdir -p "$OUTPUT_DIR"

# Load .env for GOOGLE_API_KEY
if [ -f "$DRAGONSUITE_ROOT/.env" ]; then
    set -a
    source "$DRAGONSUITE_ROOT/.env"
    set +a
fi

# Verify GOOGLE_API_KEY is set
if [ -z "${GOOGLE_API_KEY:-}" ]; then
    echo "❌ GOOGLE_API_KEY not found in .env — required for Gemini API calls"
    exit 1
fi

export GOOGLE_API_KEY
export HF_HUB_DISABLE_TELEMETRY=1
export PORT

if [ ! -f "$APP_SCRIPT" ]; then
    echo "❌ Gradio app script not found: $APP_SCRIPT"
    exit 1
fi

command -v ave >/dev/null 2>&1 || {
    echo "❌ ave CLI not found in $VENV"
    exit 1
}

echo "🚀 Starting $SERVICE_NAME (Gradio wrapper)..."
nohup python "$APP_SCRIPT" > "$LOG_FILE" 2>&1 &
SERVICE_PID=$!

if wait_for_port "$PORT" 30; then
    echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    echo "   PID: $SERVICE_PID"
    echo "   Output folder: $OUTPUT_DIR"
    echo "   Log: $LOG_FILE"
else
    echo "❌ $SERVICE_NAME failed to start on port $PORT"
    tail -80 "$LOG_FILE" 2>/dev/null || true
    exit 1
fi
