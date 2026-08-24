#!/bin/bash
# ComfyUI — node-based generative media engine, driven directly by MCP agents
# Port: 8188 (ComfyUI's own default; both comfy-mcp and the community MCP
# server auto-detect this port, so it is deliberately not remapped)
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

# GPU-optional: ComfyUI idles at near-zero VRAM until a workflow is queued.
# Actual footprint depends entirely on which workflow/model the user or an
# MCP agent loads, so there is no honest fixed number to declare here — the
# gate passes trivially and per-workflow VRAM is the user's/agent's call.
TOOL_NAME="comfyui"
REQ_VRAM_MIB=0
REQ_RAM_MIB=2000
source scripts/vram_guard.sh

SERVICE_NAME="ComfyUI"
PORT=8188
VENV="venv_comfyui"
APP_DIR="$DRAGONSUITE_ROOT/projects/ComfyUI"

service_header "$SERVICE_NAME" "$PORT"

if [ ! -f "$APP_DIR/main.py" ]; then
    echo "❌ ComfyUI not installed at $APP_DIR"
    echo "   Run: venv_comfyui/bin/comfy --workspace $APP_DIR --skip-prompt install --nvidia --cuda-version 12.8"
    exit 1
fi

vram_preflight || exit 1
clear_port "$PORT"
activate_venv "$VENV"
set_pytorch_env

echo "🚀 Starting $SERVICE_NAME..."
if pgrep -f "$APP_DIR/main.py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    cd "$APP_DIR"
    nohup python "$APP_DIR/main.py" --listen 0.0.0.0 --port "$PORT" > /tmp/comfyui.log 2>&1 &
    register_tool $!
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 120; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Not up in time — check /tmp/comfyui.log"
        tail -20 /tmp/comfyui.log
        exit 1
    fi
fi
