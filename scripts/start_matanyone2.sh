#!/bin/bash
# MatAnyone 2 - Human Video Matting
# CVPR 2026 — Interactive video alpha matte extraction
# Port 8038, LAN accessible

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/venv_matanyone2"
APP_DIR="$PROJECT_DIR/projects/matanyone2/hugging_face"

echo "✂️  MatAnyone 2"
echo "==============="
echo "Human Video Matting (CVPR 2026)"
echo ""

if [ ! -d "$VENV_DIR" ]; then
    echo "❌ venv_matanyone2 not found. Run setup first:"
    echo "   bash scripts/setup_matanyone2.sh"
    exit 1
fi

if [ ! -d "$APP_DIR" ]; then
    echo "❌ MatAnyone2 project not found at: $APP_DIR"
    echo "   git clone https://github.com/pq-yang/MatAnyone2 projects/matanyone2"
    exit 1
fi

source "$VENV_DIR/bin/activate"

export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

echo "📡 Local:   http://localhost:8038"
echo "📡 LAN:     http://192.168.7.226:8038"
echo ""
echo "Features:"
echo "  - Interactive click-to-select object on first frame (SAM)"
echo "  - Propagates alpha matte through entire video"
echo "  - Fine detail preservation (hair, fur, semi-transparent)"
echo "  - Models auto-download on first run (~2.5GB SAM + 0.5GB MatAnyone2)"
echo ""
echo "Press Ctrl+C to stop"
echo ""

cd "$APP_DIR"
python app.py --port 8038
