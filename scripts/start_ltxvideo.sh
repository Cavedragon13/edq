#!/bin/bash
# start_ltxvideo.sh — Launch LTX-Video-0.9.7-distilled (port 8028)
set -e
cd /srv/containers/edq

VENV="venv_ltxvideo"
SCRIPT="scripts/ltxvideo_gradio.py"
MODEL_DIR="models/ltxvideo"
PORT=8028

if [ ! -d "$VENV" ]; then
    echo "❌ venv_ltxvideo not found. Create it first:"
    echo "   python3 -m venv $VENV && bash scripts/download_ltxvideo_models.sh"
    exit 1
fi

if [ ! -d "$MODEL_DIR" ]; then
    echo "❌ Model not downloaded. Run: bash scripts/download_ltxvideo_models.sh"
    exit 1
fi

echo "🚀 Starting LTX-Video-0.9.7-distilled on port $PORT..."
source "$VENV/bin/activate"
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
    python "$SCRIPT"
