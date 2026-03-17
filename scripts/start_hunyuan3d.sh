#!/bin/bash
# Hunyuan3D-2 - Image to 3D Model Generation
# By Tencent
# Port 8007, LAN accessible

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
HUNYUAN3D_DIR="$PROJECT_DIR/projects/hunyuan3d"
VENV_DIR="$PROJECT_DIR/venv_hunyuan3d"
OUTPUT_DIR="$HOME/ai_generated/hunyuan3d"

echo "🧊 Hunyuan3D-2 - Image to 3D"
echo "============================"
echo "Tencent's Image-to-3D Model Generation"
echo ""

# Check for CUDA
if command -v nvidia-smi &> /dev/null; then
    echo "🎮 GPU Info:"
    nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader 2>/dev/null || echo "  (nvidia-smi unavailable)"
    echo ""
fi

# Check/create venv
if [ ! -d "$VENV_DIR" ]; then
    echo "📦 Creating virtual environment..."
    python3.12 -m venv "$VENV_DIR"
fi

# Activate venv
source "$VENV_DIR/bin/activate"

# Check if dependencies are installed
if ! python -c "import hy3dgen" 2>/dev/null; then
    echo "📦 Installing Hunyuan3D-2 dependencies..."
    echo "   This may take several minutes..."
    pip install --upgrade pip
    cd "$HUNYUAN3D_DIR"

    # Install PyTorch with CUDA
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128

    # Install requirements
    pip install -r requirements.txt
    pip install -e .

    echo "✓ Installation complete"
    echo ""
fi

HF_CACHE="${HF_HOME:-$HOME/.cache/huggingface}/hub"
SHAPE_MODEL_CACHE="$HF_CACHE/models--tencent--Hunyuan3D-2mini"
TEXGEN_MODEL_CACHE="$HF_CACHE/models--tencent--Hunyuan3D-2"

if [ ! -d "$SHAPE_MODEL_CACHE" ] || [ ! -d "$TEXGEN_MODEL_CACHE" ]; then
    echo "❌ Hunyuan3D-2 models not found in HuggingFace cache."
    echo ""
    echo "   Run the download script first:"
    echo "   bash scripts/download_hunyuan3d_models.sh"
    echo ""
    exit 1
fi

# Create output directory
mkdir -p "$OUTPUT_DIR"

echo "🌐 Starting Hunyuan3D-2 WebUI..."
echo "📡 Local:   http://localhost:8007"
echo "📡 LAN:     http://192.168.7.226:8007"
echo ""
echo "Features:"
echo "  - Image to 3D mesh generation"
echo "  - Texture synthesis"
echo "  - GLB/OBJ export"
echo "  - ~6GB VRAM for shape, ~16GB with texture"
echo ""
echo "Output saves to: $OUTPUT_DIR"
echo ""
echo "Press Ctrl+C to stop"
echo ""

cd "$HUNYUAN3D_DIR"
export HUNYUAN3D_OUTPUT_DIR="$OUTPUT_DIR"

# Memory optimization for 16GB VRAM
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

python gradio_app.py --host 0.0.0.0 --port 8007 --cache-path "$OUTPUT_DIR"
