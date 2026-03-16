#!/bin/bash
# MatAnyone 2 - One-time setup script
# Installs dependencies into venv_matanyone2

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/venv_matanyone2"
PROJECT_SRC="$PROJECT_DIR/projects/matanyone2"

echo "✂️  MatAnyone 2 Setup"
echo "===================="

if [ ! -d "$PROJECT_SRC" ]; then
    echo "📥 Cloning MatAnyone2..."
    git clone https://github.com/pq-yang/MatAnyone2 "$PROJECT_SRC"
fi

if [ ! -d "$VENV_DIR" ]; then
    echo "📦 Creating venv..."
    python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

echo "📦 Installing PyTorch (CUDA 12.8)..."
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128 -q

echo "📦 Installing MatAnyone2 core + HF app deps..."
cd "$PROJECT_SRC"
pip install -e . -q
pip install -r hugging_face/requirements.txt -q

echo "📦 Installing SAM..."
pip install git+https://github.com/facebookresearch/segment-anything.git -q

echo ""
echo "✅ Setup complete! Launch with:"
echo "   bash scripts/start_matanyone2.sh"
echo ""
echo "Note: SAM vit_h (~2.5GB) and MatAnyone2 (~0.5GB) models will"
echo "      auto-download on first launch."
