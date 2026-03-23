#!/bin/bash
# start_ltx2.sh — LTX-2.3-fp8 Video Generator (diffusers, no ComfyUI)
# Port 8016, LAN accessible

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/venv_ltxvideo"
OUTPUT_DIR="$HOME/ai_generated/ltx2"

echo "🎬 LTX-2.3 Video Generator (fp8)"
echo "================================="
echo ""

MODEL_DIR="$PROJECT_DIR/models/ltxvideo_2"
if [ ! -d "$MODEL_DIR" ]; then
    echo "❌ LTX-2 model not found at: $MODEL_DIR"
    echo "   Run: bash scripts/download_ltxvideo2_models.sh"
    exit 1
fi

# Check for CUDA
if command -v nvidia-smi &> /dev/null; then
    echo "🎮 GPU Info:"
    nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader 2>/dev/null || echo "  (nvidia-smi unavailable)"
    echo ""
fi

# Activate venv
source "$VENV_DIR/bin/activate"

# Create output directory
mkdir -p "$OUTPUT_DIR"

echo "🌐 Starting LTX-2.3 Interface..."
echo "📡 Local:   http://localhost:8016"
echo "📡 LAN:     http://192.168.7.226:8016"
echo ""
echo "Model: LTX-2.3-fp8 (diffusers, no ComfyUI)"
echo "Features:"
echo "  - Text-to-video & image-to-video"
echo "  - Multi-prompt temporal control (use | separator)"
echo "  - fp8 weights, bf16 compute, VAE tiling"
echo ""
echo "Output saves to: $OUTPUT_DIR"
echo ""
echo "Press Ctrl+C to stop"
echo ""

cd "$SCRIPT_DIR" || exit 1
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
python ltx2_gradio.py
