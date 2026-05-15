#!/bin/bash
# JustDubit — video dubbing / lip-sync service
# Port: 8022
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="JustDubit"
PORT=8022
SCRIPT="scripts/justdubit_gradio.py"
MODEL_DIR="$DRAGONSUITE_ROOT/models/justdubit"
PROJECT_VENV="$DRAGONSUITE_ROOT/projects/just-dub-it/.venv"
REQUIRED_FILES=(
    "$MODEL_DIR/ltx-2-19b-dev.safetensors"
    "$MODEL_DIR/ltx-2-19b-ic-lora-lipdubbing.safetensors"
    "$MODEL_DIR/ltx-2-19b-distilled-lora-384.safetensors"
    "$MODEL_DIR/ltx-2-spatial-upscaler-x2-1.0.safetensors"
)
GEMMA_ROOT="$MODEL_DIR/gemma-3-12b-it-qat-q4_0-unquantized"

service_header "$SERVICE_NAME" "$PORT"

missing=()
for f in "${REQUIRED_FILES[@]}"; do
    [ -f "$f" ] || missing+=("$f")
done
[ -d "$GEMMA_ROOT" ] || missing+=("$GEMMA_ROOT")
if [ "${#missing[@]}" -gt 0 ]; then
    echo "❌ JustDubit is not ready: required model assets are missing."
    printf '   - %s\n' "${missing[@]}"
    echo ""
    echo "   See: /srv/containers/edq/projects/just-dub-it/packages/ltx-pipelines/README.md"
    echo "   The dashboard currently has only the JustDubit LoRA downloaded."
    exit 1
fi

if [ ! -x "$PROJECT_VENV/bin/python" ]; then
    echo "❌ Project venv not found: $PROJECT_VENV"
    exit 1
fi

if ! "$PROJECT_VENV/bin/python" - <<'PY'
import importlib.util
raise SystemExit(0 if importlib.util.find_spec("gradio") else 1)
PY
then
    echo "❌ Gradio is not installed in JustDubit's project venv."
    echo "   Install dependencies outside the launcher before starting this service."
    exit 1
fi

gpu_preflight "$PORT"
source "$PROJECT_VENV/bin/activate"
set_pytorch_env

echo "🚀 Starting $SERVICE_NAME..."

if pgrep -f "justdubit_gradio.py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup python "$SCRIPT" > /tmp/justdubit.log 2>&1 &
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 60; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Failed — check /tmp/justdubit.log"
        tail -10 /tmp/justdubit.log
        exit 1
    fi
fi
