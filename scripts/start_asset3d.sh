#!/bin/bash
# 3D Asset Studio — image → PBR-textured GLB (Pixal3D / TRELLIS.2 int8) via ComfyUI
# Port: 8068 (UI/API).  The GPU work runs inside ComfyUI (:8188), which this
# launcher starts if it isn't already up.
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

# Honest footprint of a generation inside ComfyUI — measured 2026-09-24
# (see docs/venvs.md). The studio server itself uses no VRAM.
TOOL_NAME="asset3d"
REQ_VRAM_MIB=13600          # measured peak: Pixal3D ~12.1GB, TRELLIS.2 ~13.5GB above desktop baseline (1536 res, 4096 tex)
REQ_RAM_MIB=8000
source scripts/vram_guard.sh

SERVICE_NAME="3D Asset Studio"
PORT=8068
VENV="venv_asset3d"
COMFY_MODELS="$DRAGONSUITE_ROOT/projects/ComfyUI/models"
WORKFLOW="$DRAGONSUITE_ROOT/config/workflows/asset3d_api.json"

service_header "$SERVICE_NAME" "$PORT"

if [ ! -f "$COMFY_MODELS/diffusion_models/pixal3d_int8_convrot.safetensors" ] || [ ! -f "$COMFY_MODELS/diffusion_models/trellis_2_int8_convrot.safetensors" ]; then
    echo "❌ Models not found in $COMFY_MODELS"
    echo "   Run: bash scripts/download_asset3d_models.sh"
    exit 1
fi
if [ ! -f "$WORKFLOW" ]; then
    echo "❌ Workflow not built: $WORKFLOW"
    echo "   Run (with ComfyUI up): venv_comfyui/bin/python scripts/asset3d_build_workflow.py"
    exit 1
fi

vram_preflight || exit 1

if ! curl -s --max-time 3 -o /dev/null http://127.0.0.1:8188/system_stats; then
    echo "🔧 ComfyUI not running — starting it first"
    bash scripts/start_comfyui.sh
fi

clear_port "$PORT"
activate_venv "$VENV"
mkdir -p /home/edq/ai_generated/asset3d

echo "🚀 Starting $SERVICE_NAME..."
if pgrep -f "python scripts/asset3d_server[.]py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup python scripts/asset3d_server.py > /tmp/asset3d.log 2>&1 &
    register_tool $!
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 60; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Not up in time — check /tmp/asset3d.log"
        tail -15 /tmp/asset3d.log
        exit 1
    fi
fi
