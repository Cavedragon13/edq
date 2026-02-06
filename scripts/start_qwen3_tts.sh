#!/bin/bash
# Qwen3-TTS - Text-to-Speech with Voice Cloning and Voice Design
# Port 8009, LAN accessible

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
QWEN_TTS_DIR="$PROJECT_DIR/projects/qwen3-tts"
VENV_DIR="$PROJECT_DIR/venv_qwen3_tts"
OUTPUT_DIR="$HOME/ai_generated/qwen3-tts"

echo "🗣️ Qwen3-TTS"
echo "============"
echo "Text-to-Speech with Voice Cloning and Voice Design"
echo ""

# Check for CUDA
if command -v nvidia-smi &> /dev/null; then
    echo "🎮 GPU Info:"
    nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader 2>/dev/null || echo "  (nvidia-smi unavailable)"
    echo ""
fi

# Create project directory if needed
mkdir -p "$QWEN_TTS_DIR"

# Check/create venv
if [ ! -d "$VENV_DIR" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# Activate venv
source "$VENV_DIR/bin/activate"

# Check if qwen-tts is installed
if ! python -c "import qwen_tts" 2>/dev/null; then
    echo "📦 Installing Qwen3-TTS dependencies..."
    echo "   ⏳ This may take a few minutes..."
    echo ""
    pip install --upgrade pip
    pip install qwen-tts
    pip install "gradio>=4.0.0" soundfile

    # Try to install flash-attn for memory efficiency (optional)
    echo ""
    echo "📦 Attempting to install FlashAttention 2 (optional, for lower VRAM)..."
    pip install flash-attn --no-build-isolation 2>/dev/null || echo "   ⚠️ FlashAttention not installed (ok, will use more VRAM)"

    echo ""
    echo "✓ Installation complete"
    echo ""
fi

# Create output directory
mkdir -p "$OUTPUT_DIR"

echo "🌐 Starting Qwen3-TTS WebUI..."
echo "📡 Local:   http://localhost:8009"
echo "📡 LAN:     http://192.168.7.226:8009"
echo ""
echo "Features:"
echo "  - TTS: 9 predefined voices + style control"
echo "  - Voice Clone: Clone any voice from audio sample"
echo "  - Voice Design: Create voices from descriptions"
echo ""
echo "Note: Models are loaded on-demand (~6GB each)"
echo "      Switching features may take a moment to load"
echo ""
echo "Output saves to: $OUTPUT_DIR"
echo ""
echo "Press Ctrl+C to stop"
echo ""

cd "$QWEN_TTS_DIR"

# Memory optimization for 16GB VRAM
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

python -u app_local.py
