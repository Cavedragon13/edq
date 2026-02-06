#!/bin/bash
# Wan2GP Video Generator Launcher
# Port 8002, LAN accessible

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
WAN2GP_DIR="$PROJECT_DIR/projects/Wan2GP"
VENV_DIR="$PROJECT_DIR/venv_wan2gp"
OUTPUT_DIR="$HOME/ai_generated/wan2gp"

echo "🎬 WanGP2 Video Generator"
echo "========================="
echo ""

# Check for CUDA (don't fail if nvidia-smi has issues)
if command -v nvidia-smi &> /dev/null; then
    echo "🎮 GPU Info:"
    nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader 2>/dev/null || echo "  (nvidia-smi unavailable)"
    echo ""
fi

# Activate venv
source "$VENV_DIR/bin/activate"

# Create output directory
mkdir -p "$OUTPUT_DIR"

echo "🌐 Starting Wan2GP..."
echo "📡 Local:   http://localhost:8002"
echo "📡 LAN:     http://192.168.7.226:8002"
echo ""
echo "Recommended models for 16GB VRAM:"
echo "  - Wan 2.2 Ovi (6GB) - fastest"
echo "  - LTX 2 (8GB)"
echo "  - Flux 2 int8 (8GB)"
echo ""
echo "Output saves to: $OUTPUT_DIR"
echo ""
echo "Press Ctrl+C to stop"
echo ""

cd "$WAN2GP_DIR"
export WAN2GP_OUTPUT_DIR="$OUTPUT_DIR"
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
python wgp.py --server-name 0.0.0.0 --server-port 8002
