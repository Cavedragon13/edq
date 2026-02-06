#!/bin/bash
# Qwen-Image-Layered - Image Layer Decomposition
# Port 8013, LAN accessible

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/venv_qwen_image_layered"

echo "Qwen-Image-Layered"
echo "=================="
echo "Image Layer Decomposition for Advanced Editing"
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

    # Install diffusers from git for QwenImageLayeredPipeline support
    echo "Installing diffusers from git (for QwenImageLayeredPipeline)..."
    pip install git+https://github.com/huggingface/diffusers

    # Install other dependencies
    pip install "transformers>=4.51.3" accelerate gradio pillow python-pptx sentencepiece

    echo ""
    echo "Installation complete!"
else
    source "$VENV_DIR/bin/activate"
fi

echo ""
echo "Starting Qwen-Image-Layered..."
echo "Local:   http://localhost:8013"
echo "LAN:     http://192.168.7.226:8013"
echo ""
echo "Features:"
echo "  - Decompose images into 2-8 RGBA layers"
echo "  - Variable layer count"
echo "  - ZIP download of all layers"
echo "  - PPTX export for presentations"
echo ""
echo "VRAM: Uses ~14-16GB with CPU offloading"
echo "      Close other GPU services before use!"
echo ""
echo "Output directory: ~/ai_generated/qwen-layered/"
echo ""
echo "Press Ctrl+C to stop"
echo ""

cd "$PROJECT_DIR"

# Memory optimization for 16GB VRAM - reduce fragmentation
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

python scripts/qwen_image_layered_gradio.py
