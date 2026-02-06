#!/bin/bash
# Fish Speech TTS - OpenAudio S1-mini
# Expressive Text-to-Speech with Voice Cloning
# Port 8003, LAN accessible

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
FISH_SPEECH_DIR="$PROJECT_DIR/projects/fish-speech"
VENV_DIR="$PROJECT_DIR/venv_fish_speech"
CHECKPOINTS_DIR="$FISH_SPEECH_DIR/checkpoints"
MODEL_DIR="$CHECKPOINTS_DIR/openaudio-s1-mini"
OUTPUT_DIR="$HOME/ai_generated/fish-speech"

echo "🐟 Fish Speech TTS"
echo "=================="
echo "OpenAudio S1-mini (0.5B) - Expressive TTS with Voice Cloning"
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
    echo "📥 Downloading OpenAudio S1-mini model weights..."
    echo "   Model size: ~2GB"
    echo ""
    mkdir -p "$CHECKPOINTS_DIR"

    # Install huggingface_hub if needed
    pip install -q "huggingface_hub[cli]"

    # Try to download model
    if ! hf download fishaudio/openaudio-s1-mini --local-dir "$MODEL_DIR" 2>&1; then
        echo ""
        echo "❌ Model download failed!"
        echo ""
        echo "The OpenAudio S1-mini model is a GATED repository."
        echo "You need to accept the license agreement first:"
        echo ""
        echo "  1. Visit: https://huggingface.co/fishaudio/openaudio-s1-mini"
        echo "  2. Log in with your HuggingFace account"
        echo "  3. Click 'Agree and access repository'"
        echo "  4. Run this script again"
        echo ""
        echo "Your HF token is already cached at ~/.cache/huggingface/token"
        echo ""
        # Clean up partial download
        rm -rf "$MODEL_DIR"
        exit 1
    fi
    echo "✓ Model downloaded to $MODEL_DIR"
    echo ""
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
echo "  - Emotion control (angry, sad, excited, etc.)"
echo "  - Multi-language support"
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
    --decoder-checkpoint-path "$MODEL_DIR/codec.pth" \
    --decoder-config-name modded_dac_vq
