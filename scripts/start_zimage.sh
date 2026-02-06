#!/bin/bash
# Z-Image Base Launcher
# Port: 8011

set -e

cd /srv/containers/edq

echo "Z-Image Base - Alibaba Tongyi 6B Text-to-Image"
echo "=============================================="
echo ""

# Check if venv exists
if [ ! -d "venv_zimage" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv_zimage
    source venv_zimage/bin/activate

    echo "Installing dependencies..."
    pip install --upgrade pip

    # PyTorch with CUDA 12.8 for Blackwell (RTX 5070 Ti)
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128

    # Diffusers and dependencies
    pip install diffusers transformers accelerate
    pip install gradio==6.3.0 safetensors sentencepiece pytz
    pip install pillow

    echo ""
    echo "Virtual environment created and dependencies installed."
else
    source venv_zimage/bin/activate
fi

echo ""
echo "Starting Z-Image Base on port 8011..."
echo "Web UI: http://192.168.7.226:8011"
echo ""

# Memory optimization for 16GB VRAM
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

python scripts/zimage_base_gradio.py
