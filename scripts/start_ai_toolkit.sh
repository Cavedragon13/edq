#!/bin/bash
# AI Toolkit (Ostris) — LoRA / Fine-tune Trainer for FLUX
# Port: 8041
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

# Footprint (vram_guard). NOT independently measured 2026-11-19 — a real training
# run needs FLUX.1-schnell pulled fresh into the HF cache (23.8GB) which blew the
# unattended test budget; killed mid-download before any weights reached the GPU.
# Carried over from this service's existing vram_gb:12 config entry (set when this
# launcher was added) with ~5% headroom. Re-measure with `nvidia-smi -lms 500` during
# a real low-VRAM-mode LoRA run once the base model is cached, then tighten this.
TOOL_NAME="ai-toolkit"
REQ_VRAM_MIB=13000
REQ_RAM_MIB=12000
source scripts/vram_guard.sh

SERVICE_NAME="AI Toolkit"
PORT=8041
VENV="venv_ai_toolkit"
PROJECT="projects/ai-toolkit"

service_header "$SERVICE_NAME" "$PORT"
vram_preflight || exit 1
clear_port "$PORT"
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

# Despite the /srv/containers/edq/models/flux1-schnell cache, ai-toolkit's own
# config always resolves "schnell" to the HF repo id and pulls into ~/.cache/huggingface
# on first use (confirmed 2026-11-19) — it does not read our local models/ dir.
echo "   Base model (schnell): downloads to ~/.cache/huggingface on first use (~24GB)"
echo "   Output LoRAs → $HOME/ai_generated/ai-toolkit/"
echo ""
echo "🚀 Starting $SERVICE_NAME..."

mkdir -p "$HOME/ai_generated/ai-toolkit"

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
    register_tool $!
    if wait_for_port "$PORT" 60; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Failed — check /tmp/ai_toolkit.log"
        tail -10 /tmp/ai_toolkit.log
        exit 1
    fi
fi
