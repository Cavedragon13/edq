#!/bin/bash
# Ideogram 4 — open-weight text-to-image model
# Port: 8054
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="Ideogram 4"
PORT=8054
VENV="venv_ideogram4"
SCRIPT="scripts/ideogram4_gradio.py"
APP_DIR="$DRAGONSUITE_ROOT/projects/ideogram4"

service_header "$SERVICE_NAME" "$PORT"

if [ ! -d "$APP_DIR" ]; then
    echo "❌ Project not found: $APP_DIR"
    echo "   git clone https://github.com/ideogram-oss/ideogram4.git projects/ideogram4"
    exit 1
fi

if [ -f "$DRAGONSUITE_ROOT/.env" ]; then
    set -a
    source "$DRAGONSUITE_ROOT/.env"
    set +a
fi

if [ -z "${HF_TOKEN:-}" ] && [ -z "${HUGGING_FACE_HUB_TOKEN:-}" ]; then
    echo "❌ HF_TOKEN missing in /srv/containers/edq/.env"
    echo "   Ideogram 4 weights are gated; accept access on Hugging Face and set HF_TOKEN."
    exit 1
fi

if [ -z "${IDEOGRAM_API_KEY:-}" ] && [ -z "${MAGIC_PROMPT_API_KEY:-}" ]; then
    echo "⚠️  No Ideogram/OpenRouter magic-prompt key found; use plain or structured prompts."
fi

gpu_preflight "$PORT"
activate_venv "$VENV"
set_pytorch_env

export IDEOGRAM4_PORT=$PORT
export HF_HOME="${HF_HOME:-$DRAGONSUITE_ROOT/cache_huggingface}"
export HUGGINGFACE_HUB_CACHE="${HUGGINGFACE_HUB_CACHE:-$HF_HOME/hub}"
mkdir -p "$HOME/ai_generated/ideogram4" "$HF_HOME" "$HUGGINGFACE_HUB_CACHE"

echo "🚀 Starting $SERVICE_NAME..."
setsid python "$SCRIPT" > /tmp/ideogram4.log 2>&1 < /dev/null &

echo "⏳ Waiting for service..."
if wait_for_port "$PORT" 90; then
    echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
else
    echo "❌ Service did not start in time — check /tmp/ideogram4.log"
    tail -30 /tmp/ideogram4.log
    exit 1
fi
