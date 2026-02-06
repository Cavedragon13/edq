#!/bin/bash
# LivePortrait - Portrait Animation
# Image + Video = Animated Portrait (KlingTeam, 2024-2026)
# Port 8006, LAN accessible

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LIVEPORTRAIT_DIR="$PROJECT_DIR/projects/LivePortrait"
VENV_DIR="$PROJECT_DIR/venv_liveportrait"
OUTPUT_DIR="$HOME/ai_generated/liveportrait"

echo "🎭 LivePortrait - Portrait Animation"
echo "===================================="
echo "Image + Driving Video = Animated Portrait"
echo ""

# Check for CUDA
if command -v nvidia-smi &> /dev/null; then
    echo "GPU Info:"
    nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader 2>/dev/null || echo "  (nvidia-smi unavailable)"
    echo ""
fi

# Activate venv
source "$VENV_DIR/bin/activate"

# Create output directory
mkdir -p "$OUTPUT_DIR"

echo "Starting LivePortrait WebUI..."
echo "Local:   http://localhost:8006"
echo "LAN:     http://192.168.7.226:8006"
echo ""
echo "Features:"
echo "  - Image to animated portrait"
echo "  - Video-driven face animation"
echo "  - Expression transfer"
echo "  - Animals mode (cats & dogs)"
echo ""
echo "Output saves to: $OUTPUT_DIR"
echo ""
echo "Press Ctrl+C to stop"
echo ""

cd "$LIVEPORTRAIT_DIR"
export LIVEPORTRAIT_OUTPUT_DIR="$OUTPUT_DIR"
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export GRADIO_SERVER_NAME="0.0.0.0"
python app.py --server-port 8006 --server-name 0.0.0.0
