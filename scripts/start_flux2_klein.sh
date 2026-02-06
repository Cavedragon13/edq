#!/bin/bash
# DragonFlux Klein - FLUX.2-klein Image Generator
# Exposes on LAN via port 8001

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/venv_flux2"

echo "DragonFlux Klein"
echo "================"
echo "FLUX.2-klein Image Generator with LoRA Support"
echo ""

# Check for CUDA (don't fail if nvidia-smi has issues)
if command -v nvidia-smi &> /dev/null; then
    echo "🎮 GPU Info:"
    nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader 2>/dev/null || echo "  (nvidia-smi unavailable)"
    echo ""
fi

# Check/create venv
if [ ! -d "$VENV_DIR" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    echo "📦 Installing dependencies..."
    "$VENV_DIR/bin/pip" install -U diffusers transformers accelerate gradio torch
fi

# Activate venv
source "$VENV_DIR/bin/activate"

echo ""
echo "Starting DragonFlux Klein..."
echo "Local:   http://localhost:8001"
echo "LAN:     http://192.168.7.226:8001"
echo ""
echo "LoRA directory: ~/models/loras/flux-klein/"
echo "Output directory: ~/ai_generated/flux2-klein/"
echo ""
echo "Press Ctrl+C to stop"
echo ""

cd "$PROJECT_DIR"

# Memory optimization for 16GB VRAM
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

python scripts/flux2_klein_gradio.py
