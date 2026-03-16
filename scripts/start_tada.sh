#!/bin/bash
# TADA TTS - Hume AI open-source generative speech
# TADA-3B-ML: multilingual voice cloning, 1:1 token alignment
# Port 8037, LAN accessible

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/venv_tada"

echo "🎙️ TADA TTS (Hume AI)"
echo "======================"
echo "TADA-3B-ML — Multilingual Voice Cloning"
echo ""

if [ ! -d "$VENV_DIR" ]; then
    echo "❌ venv_tada not found. Create it first:"
    echo "   python3 -m venv $VENV_DIR"
    echo "   source $VENV_DIR/bin/activate"
    echo "   pip install hume-tada torch torchaudio --index-url https://download.pytorch.org/whl/cu128"
    echo "   pip install gradio"
    exit 1
fi

source "$VENV_DIR/bin/activate"

export GRADIO_SERVER_NAME="0.0.0.0"
export GRADIO_SERVER_PORT="8037"
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

echo "📡 Local:   http://localhost:8037"
echo "📡 LAN:     http://192.168.7.226:8037"
echo ""
echo "Features:"
echo "  - Voice cloning from reference audio (5-30s)"
echo "  - 9 language support (TADA-3B-ML)"
echo "  - Speech continuation with extra steps"
echo "  - Models auto-download from HuggingFace on first run"
echo ""
echo "Press Ctrl+C to stop"
echo ""

python "$SCRIPT_DIR/tada_gradio.py"
