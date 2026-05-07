#!/bin/bash
# Creative Upscaler — FLUX + ControlNet Tile prompt-guided upscaling
# Port: 8018
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="Creative Upscaler"
PORT=8018
VENV="venv_flux2"
SCRIPT="scripts/creative_upscale_gradio.py"
MODELS_DIR="/srv/containers/edq/models/creative_upscale"
CONTROLNET_MODEL="$MODELS_DIR/controlnet/diffusion_pytorch_model.safetensors"
FLUX_INDEX="$MODELS_DIR/flux_dev/model_index.json"
FLUX_TRANSFORMER_INDEX="$MODELS_DIR/flux_dev/transformer/diffusion_pytorch_model.safetensors.index.json"
FLUX_T5_INDEX="$MODELS_DIR/flux_dev/text_encoder_2/model.safetensors.index.json"

service_header "$SERVICE_NAME" "$PORT"
gpu_preflight "$PORT"
activate_venv "$VENV"
set_pytorch_env

# Model check — fail fast before wasting time or triggering first-run downloads.
if [ ! -s "$CONTROLNET_MODEL" ] || [ ! -s "$FLUX_INDEX" ] || [ ! -s "$FLUX_TRANSFORMER_INDEX" ] || [ ! -s "$FLUX_T5_INDEX" ]; then
    echo "❌ Complete local models not found at $MODELS_DIR"
    echo ""
    echo "Download models first (~28GB, resumable):"
    echo "  bash scripts/download_creative_upscale_models.sh"
    echo ""
    echo "This takes 20-60 minutes depending on connection speed."
    exit 1
fi
if find "$MODELS_DIR" -path '*/.cache/huggingface/download/*' -name '*.incomplete' -type f | grep -q .; then
    echo "❌ Model download is still incomplete at $MODELS_DIR"
    echo ""
    echo "Resume/finish the download first:"
    echo "  bash scripts/download_creative_upscale_models.sh"
    exit 1
fi
echo "✓ Models found"
echo ""

echo "🚀 Starting $SERVICE_NAME..."

if pgrep -f "creative_upscale_gradio.py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup python "$SCRIPT" > /tmp/creative_upscale.log 2>&1 &
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 60; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Failed — check /tmp/creative_upscale.log"
        tail -10 /tmp/creative_upscale.log
        exit 1
    fi
fi
