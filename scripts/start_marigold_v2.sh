#!/bin/bash
# Marigold V2 — depth / normals / albedo (huawei-bayerlab/marigold-v2-0) via ComfyUI
# Port: 8066  (front-end; ComfyUI itself serves on 8188)
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

# The GPU footprint belongs to ComfyUI (Q4_K_S backbone 12.2 GB + LoRA + VAE,
# ~13-14 GB peak at 1024²). This front-end holds no model, but it starts
# ComfyUI, so gate on the real requirement here.
TOOL_NAME="marigold-v2"
REQ_VRAM_MIB=13500
REQ_RAM_MIB=8000
source scripts/vram_guard.sh

SERVICE_NAME="Marigold V2"
PORT=8066
VENV="venv_marigold_v2"
SCRIPT="/srv/containers/edq/scripts/marigold_v2_gradio.py"
LOG_FILE="/tmp/marigold_v2.log"
CM="$DRAGONSUITE_ROOT/projects/ComfyUI/models"

service_header "$SERVICE_NAME" "$PORT"

for f in "unet/Qwen-Image-Edit-2509-Q4_K_S.gguf" "vae/qwen_image_vae.safetensors" \
         "loras/marigold-v2-depth-Log-stage2.safetensors" "loras/marigold-v2-normals.safetensors" \
         "loras/marigold-v2-albedo.safetensors" \
         "marigold-v2/Marigold-V2/qwen_text_embeddings/qwen_edit_2509_qwen_depth_realimg512_prompt_embeds.pt"; do
    if [ ! -f "$CM/$f" ]; then
        echo "❌ Missing $CM/$f — run: bash scripts/download_marigold_v2_models.sh"
        exit 1
    fi
done
if [ ! -d "$DRAGONSUITE_ROOT/projects/ComfyUI/custom_nodes/ComfyUI-Marigold-v2" ] || \
   [ ! -d "$DRAGONSUITE_ROOT/projects/ComfyUI/custom_nodes/ComfyUI-GGUF" ]; then
    echo "❌ ComfyUI-Marigold-v2 and ComfyUI-GGUF custom nodes are required (see docs/services/marigold-v2.md)"
    exit 1
fi

# ComfyUI first (its own launcher is idempotent and registers with the VRAM gate).
if ! curl -s --max-time 3 http://127.0.0.1:8188/system_stats > /dev/null; then
    vram_preflight || exit 1
    bash scripts/start_comfyui.sh
fi

clear_port "$PORT"
activate_venv "$VENV"
mkdir -p "$HOME/ai_generated/marigold-v2"

echo "🚀 Starting $SERVICE_NAME front-end..."
if pgrep -f "marigold_v2_gradio[.]py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup python "$SCRIPT" > "$LOG_FILE" 2>&1 &
    register_tool $!
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 90; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT  (ComfyUI backend on 8188; first prediction loads the 12 GB backbone)"
    else
        echo "❌ Service did not start in time — check $LOG_FILE"
        tail -15 "$LOG_FILE"
        exit 1
    fi
fi
