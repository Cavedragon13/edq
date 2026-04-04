#!/bin/bash
# LTX-2.3-fp8 Video Generator — diffusers, no ComfyUI
# Port: 8016
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="LTX-2.3 Video Generator"
PORT=8016
VENV="venv_ltxvideo"
SCRIPT="scripts/ltx2_gradio.py"
MODEL_DIR="models/ltxvideo_2"
OUTPUT_DIR="$HOME/ai_generated/ltx2"

service_header "$SERVICE_NAME" "$PORT"

if [ ! -d "$MODEL_DIR" ]; then
    echo "❌ LTX-2 model not found at: $MODEL_DIR"
    echo "   Run: bash scripts/download_ltxvideo2_models.sh"
    exit 1
fi

gpu_preflight "$PORT"
activate_venv "$VENV"
set_pytorch_env

mkdir -p "$OUTPUT_DIR"

echo "Model: LTX-2.3-fp8 (diffusers, no ComfyUI)"
echo "Features:"
echo "  - Text-to-video & image-to-video"
echo "  - Multi-prompt temporal control (use | separator)"
echo "  - fp8 weights, bf16 compute, VAE tiling"
echo ""
echo "Output saves to: $OUTPUT_DIR"
echo ""
echo "🚀 Starting $SERVICE_NAME..."

if pgrep -f "ltx2_gradio.py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup python "$SCRIPT" > /tmp/ltx2.log 2>&1 &
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 60; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Service did not start in time — check /tmp/ltx2.log"
        tail -10 /tmp/ltx2.log
        exit 1
    fi
fi
