#!/bin/bash
set -e

echo "🐬 Starting Dolphin Vision 7B..."

MODEL_PATH="/srv/containers/edq/models/dolphin-vision-7b"
VENV_PATH="/srv/containers/edq/venv_dolphin_vision"

# Check model exists
if [ ! -d "$MODEL_PATH" ]; then
    echo "❌ Model not found at $MODEL_PATH"
    echo ""
    echo "Download with:"
    echo "  source $VENV_PATH/bin/activate"
    echo "  huggingface-cli download cognitivecomputations/dolphin-vision-7b --local-dir $MODEL_PATH"
    exit 1
fi

# Check venv exists
if [ ! -d "$VENV_PATH" ]; then
    echo "❌ venv not found at $VENV_PATH"
    echo ""
    echo "Create with:"
    echo "  python3 -m venv $VENV_PATH"
    echo "  source $VENV_PATH/bin/activate"
    echo "  pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128"
    echo "  pip install transformers gradio pillow accelerate"
    exit 1
fi

# Memory optimization
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

source "$VENV_PATH/bin/activate"

echo "✓ Model found: $(du -sh $MODEL_PATH | cut -f1)"
echo "✓ venv activated"
echo ""
echo "📍 Access at: http://192.168.7.226:8025"
echo ""
echo "Note: First query loads model (~30s, ~12GB VRAM)"
echo "      Close other GPU services before starting."
echo ""

python /srv/containers/edq/scripts/dolphin_vision_gradio.py
