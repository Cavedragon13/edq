#!/bin/bash
# Wan2GP Video Generator
# Port: 8002
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="Wan2GP Video Generator"
PORT=8002
VENV="venv_wan2gp"
WAN2GP_DIR="$DRAGONSUITE_ROOT/projects/Wan2GP"
OUTPUT_DIR="$HOME/ai_generated/wan2gp"
LOG_FILE="/tmp/wan2gp.log"

service_header "$SERVICE_NAME" "$PORT"
gpu_preflight "$PORT"
activate_venv "$VENV"
set_pytorch_env

mkdir -p "$OUTPUT_DIR"

echo "Recommended models for 16GB VRAM:"
echo "  - Wan 2.2 Ovi (6GB) - fastest"
echo "  - LTX 2 (8GB)"
echo "  - Flux 2 int8 (8GB)"
echo ""
echo "Output saves to: $OUTPUT_DIR"
echo ""
echo "🚀 Starting $SERVICE_NAME..."

# Background launch with a readiness wait (house pattern). The previous
# foreground `python wgp.py` never returned, so weekly_update.sh's
# launch-verify timed out and rolled the code back every single week, and
# the Dashboard stop button had no matching background process to kill.
cd "$WAN2GP_DIR"
if pgrep -f "python.*wgp.py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup python "$WAN2GP_DIR/wgp.py" --server-name 0.0.0.0 --server-port "$PORT" > "$LOG_FILE" 2>&1 &
    echo "⏳ Waiting for service (log: $LOG_FILE)..."
    if wait_for_port "$PORT" 180; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Service did not start in time — check $LOG_FILE"
        tail -10 "$LOG_FILE"
        exit 1
    fi
fi
