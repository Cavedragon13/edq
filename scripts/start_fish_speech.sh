#!/bin/bash
# Fish Speech TTS - S2-Pro
# Expressive Text-to-Speech with Voice Cloning
# Port 8003, LAN accessible
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="Fish Speech TTS"
PORT=8003
VENV="venv_fish_speech"

FISH_SPEECH_DIR="$DRAGONSUITE_ROOT/projects/fish-speech"
MODEL_DIR="$FISH_SPEECH_DIR/checkpoints/s2-pro"
OUTPUT_DIR="$HOME/ai_generated/fish-speech"

service_header "$SERVICE_NAME" "$PORT"

# Check model weights before evicting GPU. Do not download on first launch.
if [ ! -d "$MODEL_DIR" ] || [ ! -f "$MODEL_DIR/codec.pth" ] || ! ls "$MODEL_DIR"/model-*.safetensors >/dev/null 2>&1; then
    echo "❌ Fish Speech S2-Pro model weights are missing at $MODEL_DIR"
    echo "   Run the model download/setup step outside the launcher, then retry."
    exit 1
fi

gpu_preflight "$PORT"
activate_venv "$VENV"

# Check if fish-speech is installed. Do not install on first launch.
if ! python -c "import fish_speech" 2>/dev/null; then
    echo "❌ fish_speech is not installed in $VENV"
    echo "   Install project dependencies outside the launcher, then retry."
    exit 1
fi

set_pytorch_env
export GRADIO_SERVER_NAME="0.0.0.0"
export GRADIO_SERVER_PORT="$PORT"
export FISH_SPEECH_OUTPUT_DIR="$OUTPUT_DIR"
# S2-Pro's static KV cache defaults to the full 32768-token max_seq_len
# (~4.5GB) regardless of actual request length — right at the edge of a
# 16GB card once weights + decoder are loaded. 8192 still covers far more
# than a typical TTS clip and frees ~3.4GB.
export FISH_SPEECH_MAX_SEQ_LEN="${FISH_SPEECH_MAX_SEQ_LEN:-8192}"
# The DAC decoder's 3 internal transformer sub-blocks each hardcode a
# (32768x32768) bool causal_mask (~1GB each, ~3GB total) despite their own
# configs using block_size 2048-8192. 16384 is 2x the largest documented
# block_size — generous headroom for this deployment's short-clip TTS use,
# while freeing ~2.6GB.
export FISH_SPEECH_DAC_CAUSAL_MASK_SIZE="${FISH_SPEECH_DAC_CAUSAL_MASK_SIZE:-16384}"

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
