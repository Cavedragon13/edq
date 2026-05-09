#!/bin/bash
set -e

cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="DeepGen 1.0"
PORT=8024
VENV_PATH="/srv/containers/edq/venv_deepgen"
MODELS_DIR="/srv/containers/edq/models/deepgen-1.0-diffusers"
SCRIPT="scripts/deepgen_diffusers_gradio.py"

service_header "$SERVICE_NAME" "$PORT"

if [ ! -d "$VENV_PATH" ]; then
    echo "❌ venv_deepgen not found at $VENV_PATH"
    echo "   Run: bash scripts/setup_deepgen_diffusers.sh"
    exit 1
fi

if [ ! -s "$MODELS_DIR/model_index.json" ] || [ ! -s "$MODELS_DIR/deepgen_pipeline.py" ] || [ ! -s "$MODELS_DIR/transformer/diffusion_pytorch_model.safetensors" ]; then
    echo "❌ Complete DeepGen diffusers model not found at $MODELS_DIR"
    echo "   Run: bash scripts/download_deepgen_models.sh"
    exit 1
fi

if find "$MODELS_DIR" -path '*/.cache/huggingface/download/*' -name '*.incomplete' -type f | grep -q .; then
    echo "❌ DeepGen model download is incomplete at $MODELS_DIR"
    echo "   Re-run: bash scripts/download_deepgen_models.sh"
    exit 1
fi

gpu_preflight "$PORT"
source "$VENV_PATH/bin/activate"
set_pytorch_env
mkdir -p "$HOME/ai_generated/deepgen"

echo "🚀 Starting $SERVICE_NAME..."
if pgrep -f "deepgen_diffusers_gradio.py" > /dev/null; then
    if curl -s --max-time 2 "http://127.0.0.1:$PORT/" > /dev/null 2>&1; then
        echo "✓ Already running on port $PORT"
    else
        echo "⚠️  Found stale DeepGen process without a listening port; stopping it..."
        pkill -f "deepgen_diffusers_gradio.py" || true
        sleep 2
        nohup python "$SCRIPT" > /tmp/deepgen.log 2>&1 &
        echo "⏳ Waiting for service..."
        if wait_for_port "$PORT" 120; then
            echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
        else
            echo "❌ Not up in time — check /tmp/deepgen.log"
            tail -30 /tmp/deepgen.log
            exit 1
        fi
    fi
else
    nohup python "$SCRIPT" > /tmp/deepgen.log 2>&1 &
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 120; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Not up in time — check /tmp/deepgen.log"
        tail -30 /tmp/deepgen.log
        exit 1
    fi
fi
