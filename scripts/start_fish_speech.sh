#!/bin/bash
# Fish Speech TTS - OpenAudio S1-mini
# Expressive Text-to-Speech with Voice Cloning
# Port 8003, LAN accessible
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="Fish Speech TTS"
PORT=8003
VENV="venv_fish_speech"

FISH_SPEECH_DIR="$DRAGONSUITE_ROOT/projects/fish-speech"
MODEL_DIR="$FISH_SPEECH_DIR/checkpoints/openaudio-s1-mini"
OUTPUT_DIR="$HOME/ai_generated/fish-speech"

service_header "$SERVICE_NAME" "$PORT"

# Check/download model weights before evicting GPU
if [ ! -d "$MODEL_DIR" ] || [ ! -f "$MODEL_DIR/codec.pth" ]; then
    echo "📥 Downloading OpenAudio S1-mini model weights..."
    echo "   Model size: ~2GB"
    echo ""
    mkdir -p "$FISH_SPEECH_DIR/checkpoints"

    # Activate venv early just for the download
    activate_venv "$VENV"
    pip install -q "huggingface_hub[cli]"

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
        rm -rf "$MODEL_DIR"
        exit 1
    fi
    echo "✓ Model downloaded to $MODEL_DIR"
    echo ""
fi

gpu_preflight "$PORT"
activate_venv "$VENV"

# Check if fish-speech is installed
if ! python -c "import fish_speech" 2>/dev/null; then
    echo "📦 Installing Fish Speech with CUDA support..."
    echo "   This may take a few minutes on first run..."
    (cd "$FISH_SPEECH_DIR" && pip install --upgrade pip && pip install -e ".[cu129]")
    echo "✓ Installation complete"
    echo ""
fi

set_pytorch_env
export GRADIO_SERVER_NAME="0.0.0.0"
export GRADIO_SERVER_PORT="$PORT"
export FISH_SPEECH_OUTPUT_DIR="$OUTPUT_DIR"

mkdir -p "$FISH_SPEECH_DIR/references"
mkdir -p "$OUTPUT_DIR"

echo "🚀 Starting $SERVICE_NAME..."
if pgrep -f "tools.run_webui.*$MODEL_DIR" > /dev/null && ss -ltn "( sport = :$PORT )" | grep -q LISTEN; then
    echo "✓ Already running on port $PORT"
else
    cd "$FISH_SPEECH_DIR"
    nohup python -m tools.run_webui \
        --llama-checkpoint-path "$MODEL_DIR" \
        --decoder-checkpoint-path "$MODEL_DIR/codec.pth" \
        --decoder-config-name modded_dac_vq \
        > /tmp/fish_speech.log 2>&1 &
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 60; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Service did not start in time — check /tmp/fish_speech.log"
        tail -10 /tmp/fish_speech.log
        exit 1
    fi
fi
