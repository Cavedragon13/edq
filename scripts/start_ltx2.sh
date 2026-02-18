#!/bin/bash
# LTX-2 Dedicated Video Generator Launcher
# Port 8016, LAN accessible

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/venv_wan2gp"
OUTPUT_DIR="$HOME/ai_generated/ltx2"

echo "🎬 LTX-2 Video Generator"
echo "========================"
echo ""

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

echo "🌐 Starting LTX-2 Interface..."
echo "📡 Local:   http://localhost:8016"
echo "📡 LAN:     http://192.168.7.226:8016"
echo ""
echo "Model: LTX-2 Dev 19B"
echo "Features:"
echo "  - 20 second video with audio"
echo "  - Start/end keyframes"
echo "  - Audio soundtrack generation"
echo ""
echo "Output saves to: $OUTPUT_DIR"
echo ""
echo "Press Ctrl+C to stop"
echo ""

cd "$SCRIPT_DIR"
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
python ltx2_gradio.py
