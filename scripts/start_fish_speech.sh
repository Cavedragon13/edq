#!/bin/bash
# Fish Speech TTS - Fish Audio S2-Pro
# 4B Dual-AR Model with Expressive TTS and Voice Cloning
# Port 8003, LAN accessible

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
FISH_SPEECH_DIR="$PROJECT_DIR/projects/fish-speech"
VENV_DIR="$PROJECT_DIR/venv_fish_speech"
CHECKPOINTS_DIR="$FISH_SPEECH_DIR/checkpoints"
MODEL_DIR="$CHECKPOINTS_DIR/s2-pro"
OUTPUT_DIR="$HOME/ai_generated/fish-speech"

echo "🐟 Fish Speech TTS"
echo "=================="
echo "Fish Audio S2-Pro (4B) - Expressive TTS with Voice Cloning"
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

# Check if fish-speech is installed
if ! python -c "import fish_speech" 2>/dev/null; then
    echo "📦 Installing Fish Speech with CUDA support..."
    echo "   This may take a few minutes on first run..."
    cd "$FISH_SPEECH_DIR"
    pip install --upgrade pip
    pip install -e ".[cu129]"
    echo "✓ Installation complete"
    echo ""
fi

# Check/download model weights
if [ ! -d "$MODEL_DIR" ] || [ ! -f "$MODEL_DIR/codec.pth" ]; then
    echo "❌ Fish Audio S2-Pro model not found at: $MODEL_DIR"
    echo ""
    echo "   Run the download script first:"
    echo "   bash scripts/download_fish_speech_s2_models.sh"
    echo ""
    exit 1
fi

# Create references and output directories
mkdir -p "$FISH_SPEECH_DIR/references"
mkdir -p "$OUTPUT_DIR"

echo "🌐 Starting Fish Speech WebUI..."
echo "📡 Local:   http://localhost:8003"
echo "📡 LAN:     http://192.168.7.226:8003"
echo ""
echo "Features:"
echo "  - Zero-shot TTS (no reference needed)"
echo "  - Voice cloning (10-30s sample)"
echo "  - Inline emotion control [laugh] [whisper] etc."
echo "  - 50+ language support (S2-Pro)"
echo ""
echo "Reference audio: $FISH_SPEECH_DIR/references/"
echo "Output saves to: $OUTPUT_DIR"
echo ""
echo "Press Ctrl+C to stop"
echo ""

cd "$FISH_SPEECH_DIR"
export GRADIO_SERVER_NAME="0.0.0.0"
export GRADIO_SERVER_PORT="8003"
export FISH_SPEECH_OUTPUT_DIR="$OUTPUT_DIR"

# Memory optimization for 16GB VRAM
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

python -m tools.run_webui \
    --llama-checkpoint-path "$MODEL_DIR" \
    --decoder-checkpoint-path "$MODEL_DIR/codec.pth"
