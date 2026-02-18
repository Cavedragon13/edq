#!/bin/bash
set -e

echo "🎨 Starting DeepGen 1.0..."

VENV_PATH="/srv/containers/edq/venv_deepgen"
CHECKPOINT="/srv/containers/edq/models/deepgen-1.0/model.pt"
MODEL_ZOO="/srv/containers/edq/projects/deepgen/model_zoo"

if [ ! -d "$VENV_PATH" ]; then
    echo "❌ venv_deepgen not found at $VENV_PATH"
    exit 1
fi

if [ ! -f "$CHECKPOINT" ]; then
    echo "❌ Checkpoint not found: $CHECKPOINT"
    exit 1
fi

if [ ! -d "$MODEL_ZOO" ] && [ ! -L "$MODEL_ZOO" ]; then
    echo "❌ model_zoo not found at $MODEL_ZOO"
    echo ""
    echo "Run the model zoo setup first:"
    echo "  bash scripts/download_deepgen_model_zoo.sh"
    exit 1
fi

source "$VENV_PATH/bin/activate"
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

echo "✓ Checkpoint: $CHECKPOINT"
echo "✓ model_zoo:  $MODEL_ZOO"
echo ""
echo "📍 Access at: http://192.168.7.226:8024"
echo ""
echo "Tabs:"
echo "  🖼️ Text-to-Image  - Generate from prompt"
echo "  ✏️ Image Editing  - Edit with instructions"
echo ""
echo "NOTE: Model loads on first generate (~30s, ~11GB VRAM)"
echo ""

python /srv/containers/edq/scripts/deepgen_gradio.py
