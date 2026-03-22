#!/bin/bash
set -e

PROJECT_DIR="/srv/containers/edq/projects/foundation-1"
MODEL="/srv/containers/edq/projects/foundation-1/models/Foundation_1.safetensors"
CONFIG="/srv/containers/edq/projects/foundation-1/models/model_config.json"
PORT=8039

if [ ! -f "$MODEL" ]; then
    echo "❌ Foundation-1 model not found: $MODEL"
    echo "   Run: bash scripts/download_foundation1_models.sh"
    exit 1
fi

source /srv/containers/edq/venv_foundation1/bin/activate

export GRADIO_SERVER_PORT=$PORT
export GRADIO_SERVER_NAME="0.0.0.0"
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

echo "🎵 Starting Foundation-1 on port $PORT..."
cd "$PROJECT_DIR"
exec python run_gradio.py \
    --model-config "$CONFIG" \
    --ckpt-path "$MODEL" \
    --model-half \
    --title "Foundation-1"
