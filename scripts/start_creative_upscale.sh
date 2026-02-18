#!/bin/bash
set -e

echo "🎨 Starting Creative Upscaler (FLUX + ControlNet Tile)..."

# Memory optimization
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

# Activate FLUX venv (already has diffusers, torch, etc.)
source /srv/containers/edq/venv_flux2/bin/activate

# Install additional dependencies if needed
pip install -q diffusers[torch]>=0.30.0 --upgrade 2>/dev/null || true

# Check GPU
if ! python -c "import torch; assert torch.cuda.is_available()" 2>/dev/null; then
    echo "❌ CUDA not available!"
    exit 1
fi

echo "✓ GPU detected"
echo "⚠️  Close other GPU services if VRAM is low (<4GB free)"
echo ""

# Check if models exist
MODELS_DIR="/srv/containers/edq/models/creative_upscale"
if [ ! -d "$MODELS_DIR/controlnet" ] || [ ! -d "$MODELS_DIR/flux_dev" ]; then
    echo "❌ Models not found at $MODELS_DIR"
    echo ""
    echo "Download models first (~28GB, resumable):"
    echo "  bash scripts/download_creative_upscale_models.sh"
    echo ""
    echo "This takes 20-60 minutes depending on connection speed."
    echo "Safe to interrupt (Ctrl+C) and resume later."
    exit 1
fi

echo "✓ Models found"
echo ""

# Launch
python /srv/containers/edq/scripts/creative_upscale_gradio.py
