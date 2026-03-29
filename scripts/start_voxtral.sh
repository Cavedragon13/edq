#!/bin/bash
# Voxtral TTS — start vLLM-Omni backend (port 9042) + Gradio UI (port 8042)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
VENV="$ROOT_DIR/venv_voxtral"
MODEL_ID="mistralai/Voxtral-4B-TTS-2603"
BACKEND_PORT=9042
UI_PORT=8042
PID_FILE="/tmp/voxtral_backend.pid"

source "$VENV/bin/activate"

# Check model is downloaded
python3 -c "
from huggingface_hub import try_to_load_from_cache
result = try_to_load_from_cache('$MODEL_ID', 'config.json')
if result is None or result == 'config.json':
    print('ERROR: Model not found in cache. Run scripts/download_voxtral_models.sh first.')
    exit(1)
print('Model found in cache.')
" || exit 1

# Kill any existing backend
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    kill "$OLD_PID" 2>/dev/null && echo "Stopped existing backend (PID $OLD_PID)" || true
    rm -f "$PID_FILE"
fi

echo "🚀 Starting vLLM-Omni backend on port $BACKEND_PORT..."
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
HF_HUB_OFFLINE=1 \
vllm serve "$MODEL_ID" \
    --omni \
    --host 127.0.0.1 \
    --port "$BACKEND_PORT" \
    --dtype bfloat16 \
    --max-model-len 4096 \
    > /tmp/voxtral_backend.log 2>&1 &

BACKEND_PID=$!
echo "$BACKEND_PID" > "$PID_FILE"
echo "Backend PID: $BACKEND_PID (log: /tmp/voxtral_backend.log)"

# Wait for backend to be ready (up to 3 minutes for model load)
echo "Waiting for backend to be ready..."
MAX_WAIT=180
WAITED=0
while [ "$WAITED" -lt "$MAX_WAIT" ]; do
    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
        echo "❌ Backend process died. Check /tmp/voxtral_backend.log"
        exit 1
    fi
    if curl -sf "http://127.0.0.1:$BACKEND_PORT/health" > /dev/null 2>&1; then
        echo "✓ Backend ready after ${WAITED}s"
        break
    fi
    sleep 5
    WAITED=$((WAITED + 5))
done

if [ "$WAITED" -ge "$MAX_WAIT" ]; then
    echo "❌ Backend did not become ready within ${MAX_WAIT}s. Check /tmp/voxtral_backend.log"
    exit 1
fi

echo "🎙️ Starting Gradio UI on port $UI_PORT..."
VOXTRAL_BACKEND_URL="http://127.0.0.1:$BACKEND_PORT" \
VOXTRAL_PORT="$UI_PORT" \
python3 "$SCRIPT_DIR/voxtral_server.py"
