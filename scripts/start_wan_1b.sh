#!/bin/bash
# start_wan_1b.sh — Launch Wan2.1-T2V-1.3B (port 8016)
set -e
cd /srv/containers/edq

VENV="venv_wan_1b"
SCRIPT="scripts/wan_1b_gradio.py"
MODEL_DIR="models/wan_1b"
PORT=8016

if [ ! -d "$VENV" ]; then
    echo "❌ venv_wan_1b not found. Create it first:"
    echo "   python3 -m venv $VENV && bash scripts/download_wan_1b_models.sh"
    exit 1
fi

if [ ! -d "$MODEL_DIR/transformer" ]; then
    echo "❌ Model not downloaded. Run: bash scripts/download_wan_1b_models.sh"
    exit 1
fi

echo "🚀 Starting Wan2.1-T2V-1.3B on port $PORT..."
source "$VENV/bin/activate"
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
    python "$SCRIPT"
