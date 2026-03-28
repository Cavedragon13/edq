#!/bin/bash
# AI Toolkit (Ostris) — LoRA / Fine-tune Trainer for FLUX
# Port: 8041, LAN accessible

set -e

cd /srv/containers/edq

VENV="venv_ai_toolkit"
PROJECT="projects/ai-toolkit"
PORT=8041

echo "🎨 AI Toolkit — LoRA Trainer"
echo "============================="
echo ""

if [ ! -d "$VENV" ]; then
    echo "❌ venv_ai_toolkit not found."
    echo "   python3 -m venv $VENV"
    echo "   source $VENV/bin/activate"
    echo "   pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128"
    echo "   pip install -r $PROJECT/requirements.txt"
    exit 1
fi

# Warn if Florence-2 captioning model is missing (not fatal)
FLORENCE_CACHE="$HOME/.cache/huggingface/hub/models--multimodalart--Florence-2-large-no-flash-attn"
if [ ! -d "$FLORENCE_CACHE" ]; then
    echo "⚠️  Florence-2 captioning model not yet downloaded."
    echo "   Run: bash scripts/download_ai_toolkit_models.sh"
    echo "   (AI captions unavailable until then; manual captions still work)"
    echo ""
fi

source "$VENV/bin/activate"

python3 -c "import torch; print(f'   PyTorch {torch.__version__}  CUDA: {torch.cuda.is_available()}')"
echo ""
echo "🚀 Starting on port $PORT..."
echo "   http://192.168.7.226:$PORT"
echo ""
echo "   Base model (schnell, local): /srv/containers/edq/models/flux1-schnell"
echo "   Output LoRAs → /srv/containers/edq/models/loras/"
echo ""

export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

cd "$PROJECT"
exec python3 -c "
import sys, os
sys.path.insert(0, os.getcwd())
from flux_train_ui import demo
demo.launch(
    server_name='0.0.0.0',
    server_port=$PORT,
    share=False,
    show_error=True,
)
"
