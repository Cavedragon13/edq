#!/bin/bash
# Real-ESRGAN Upscaler
# Exposes on LAN via port 8010

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/venv_realesrgan"

echo "Real-ESRGAN Upscaler"
echo "===================="
echo "AI Image Upscaling with Face Enhancement"
echo ""

# Check for CUDA
if command -v nvidia-smi &> /dev/null; then
    echo "GPU Info:"
    nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader 2>/dev/null || echo "  (nvidia-smi unavailable)"
    echo ""
fi

# Check/create venv
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"

    echo "Installing dependencies..."
    pip install -U pip wheel

    # Install PyTorch with CUDA 12.8 (required for RTX 5070 Ti / Blackwell sm_120)
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128

    # Install Real-ESRGAN and dependencies
    pip install realesrgan basicsr gfpgan gradio opencv-python-headless pillow numpy

    # Patch basicsr for torchvision compatibility (functional_tensor removed in newer versions)
    DEGRADATIONS_FILE="$VENV_DIR/lib/python3.12/site-packages/basicsr/data/degradations.py"
    if grep -q "functional_tensor" "$DEGRADATIONS_FILE" 2>/dev/null; then
        sed -i 's/from torchvision.transforms.functional_tensor import rgb_to_grayscale/from torchvision.transforms.functional import rgb_to_grayscale/' "$DEGRADATIONS_FILE"
        echo "Patched basicsr for torchvision compatibility"
    fi

    echo ""
    echo "Installation complete!"
else
    source "$VENV_DIR/bin/activate"
fi

echo ""
echo "Starting Real-ESRGAN Upscaler..."
echo "Local:   http://localhost:8010"
echo "LAN:     http://192.168.7.226:8010"
echo ""
echo "Models: RealESRGAN_x4plus, RealESRGAN_x4plus_anime_6B, RealESRGAN_x2plus"
echo "Output directory: ~/ai_generated/realesrgan/"
echo ""
echo "Press Ctrl+C to stop"
echo ""

cd "$PROJECT_DIR"

# Memory optimization for 16GB VRAM
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

python scripts/realesrgan_gradio.py
