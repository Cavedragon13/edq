#!/bin/bash
# AI Toolkit (Ostris) — LoRA / Fine-tune Trainer for FLUX
# Port: 8041
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="AI Toolkit"
PORT=8041
VENV="venv_ai_toolkit"
PROJECT="projects/ai-toolkit"

service_header "$SERVICE_NAME" "$PORT"
gpu_preflight "$PORT"
activate_venv "$VENV"
set_pytorch_env

# Warn if Florence-2 captioning model is missing (not fatal)
FLORENCE_CACHE="$HOME/.cache/huggingface/hub/models--multimodalart--Florence-2-large-no-flash-attn"
if [ ! -d "$FLORENCE_CACHE" ]; then
    echo "⚠️  Florence-2 captioning model not yet downloaded."
    echo "   Run: bash scripts/download_ai_toolkit_models.sh"
    echo "   (AI captions unavailable until then; manual captions still work)"
    echo ""
fi

echo "   Base model (schnell, local): /srv/containers/edq/models/flux1-schnell"
echo "   Output LoRAs → /srv/containers/edq/models/loras/"
echo ""
echo "🚀 Starting $SERVICE_NAME..."

if pgrep -f "flux_train_ui" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    cd "$PROJECT"
    nohup python3 -c "
import sys, os
sys.path.insert(0, os.getcwd())
import gradio.networking as networking
from flux_train_ui import demo

# Gradio 4.44 can reject 0.0.0.0 launches when its localhost self-check runs
# in this dashboard environment. Keep the service LAN-local and avoid public
# share tunnels by bypassing only that self-check.
networking.url_ok = lambda url: True
# The upstream UI exposes component schemas that Gradio 4.44's API-info
# converter cannot parse. The dashboard only needs the browser UI, so disable
# API schema generation for this wrapper.
demo.get_api_info = lambda: {}

demo.launch(
    server_name='0.0.0.0',
    server_port=$PORT,
    share=False,
    show_error=True,
    show_api=False,
)
" > /tmp/ai_toolkit.log 2>&1 &
    if wait_for_port "$PORT" 60; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Failed — check /tmp/ai_toolkit.log"
        tail -10 /tmp/ai_toolkit.log
        exit 1
    fi
fi
