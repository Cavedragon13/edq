#!/bin/bash
set -e

echo "🎵 Starting Audio Processing Suite..."

VENV_PATH="/srv/containers/edq/venv_soulxsinger"
PREPROCESS_BASE="/srv/containers/edq/models/SoulX-Singer-Preprocess"

# Check venv exists
if [ ! -d "$VENV_PATH" ]; then
    echo "❌ venv_soulxsinger not found at $VENV_PATH"
    echo "Create it first (see docs/venvs.md)."
    exit 1
fi

# Check models exist
if [ ! -d "$PREPROCESS_BASE/mel-band-roformer-karaoke" ]; then
    echo "❌ Preprocessing models not found at $PREPROCESS_BASE"
    echo ""
    echo "Download with:"
    echo "  bash scripts/download_soulxsinger_models.sh"
    exit 1
fi

# Memory optimization
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

source "$VENV_PATH/bin/activate"

echo "✓ Models found at: $PREPROCESS_BASE"
echo "✓ venv_soulxsinger activated"
echo ""
echo "📍 Access at: http://192.168.7.226:8026"
echo ""
echo "Tabs:"
echo "  🎤 Karaoke Maker     - Vocal/instrumental stem separation"
echo "  🎙️ Vocal Dereverb    - Remove room reverb from vocals"
echo "  📝 Speech-to-Text    - EN/ZH/YUE transcription with timestamps"
echo ""
echo "Models load on first use per tab."
echo ""

python /srv/containers/edq/scripts/audio_tools_gradio.py
