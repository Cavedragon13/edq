#!/bin/bash
# Qwen3-TTS - Text-to-Speech with Voice Cloning and Voice Design
# Port 8009, LAN accessible
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="Qwen3-TTS"
PORT=8009
VENV="venv_qwen3_tts"

QWEN_TTS_DIR="$DRAGONSUITE_ROOT/projects/qwen3-tts"
OUTPUT_DIR="$HOME/ai_generated/qwen3-tts"
export NUMBA_CACHE_DIR="/tmp/numba-qwen3-tts"
mkdir -p "$NUMBA_CACHE_DIR"

service_header "$SERVICE_NAME" "$PORT"
gpu_preflight "$PORT"
activate_venv "$VENV"

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

set_pytorch_env
mkdir -p "$QWEN_TTS_DIR"
mkdir -p "$OUTPUT_DIR"

echo "🚀 Starting $SERVICE_NAME..."
if pgrep -f "qwen3-tts/app_local.py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    cd "$QWEN_TTS_DIR"
    nohup python -u app_local.py > /tmp/qwen3_tts.log 2>&1 &
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 60; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Service did not start in time — check /tmp/qwen3_tts.log"
        tail -10 /tmp/qwen3_tts.log
        exit 1
    fi
fi
