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

# Launch
python /srv/containers/edq/scripts/creative_upscale_gradio.py
