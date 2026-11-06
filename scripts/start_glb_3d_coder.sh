#!/bin/bash
# GLB-3D-Coder Studio — text prompt to low-poly Three.js asset + GLB export (CCORE Qwen3.5-4B)
# Port: 8022 UI (free slot in the Dragonsuite 8000-8099 range at install, 2026-11-06)
#       18022 llama-server (localhost only; the UI talks to it, nothing else should)
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

# Footprint: Q8_0 GGUF (4.5GB) fully on GPU + KV cache for a 96K context.
# Measured 2026-11-06: llama-server 7,804MiB VRAM (flat: KV is allocated up front), RSS ~1.2GB +
# UI ~150MB. A 12K-token asset took 87s at 139 tok/s. GLB3D_CTX=49152 roughly halves the KV share.
TOOL_NAME="glb-3d-coder"
REQ_VRAM_MIB=8000
REQ_RAM_MIB=2000
source scripts/vram_guard.sh

SERVICE_NAME="GLB-3D-Coder Studio"
PORT=8022
LLM_PORT=18022
CTX="${GLB3D_CTX:-98304}"     # trained on answers up to 72K tokens; average ~20K
VENV="venv_glb_3d_coder"
MODEL="$DRAGONSUITE_ROOT/models/glb-3d-coder/Qwen3.5-4B-GLB-3D-Coder-Q8_0.gguf"
LLAMA_SERVER="$DRAGONSUITE_ROOT/projects/llama.cpp/build/bin/llama-server"
OUT_DIR="/home/edq/ai_generated/glb-3d-coder"
APP="$DRAGONSUITE_ROOT/scripts/glb_3d_coder_app.py"
LOG="/srv/containers/edq/logs/glb_3d_coder_server.log"
LLM_LOG="/srv/containers/edq/logs/glb_3d_coder_llama.log"

service_header "$SERVICE_NAME" "$PORT"

if [ ! -f "$MODEL" ]; then
    echo "❌ Model not found — run: bash scripts/download_glb_3d_coder_models.sh"
    exit 1
fi
if [ ! -x "$LLAMA_SERVER" ]; then
    echo "❌ llama-server not built at $LLAMA_SERVER (needs Qwen3.5 support, llama.cpp >= Aug 2026)"
    exit 1
fi

if curl -s --max-time 2 "http://127.0.0.1:$PORT" > /dev/null 2>&1; then
    echo "✓ Already running on port $PORT"
    exit 0
fi

mkdir -p "$OUT_DIR" "$(dirname "$LOG")"

if curl -s --max-time 2 "http://127.0.0.1:$LLM_PORT/health" > /dev/null 2>&1; then
    echo "✓ llama-server already up on $LLM_PORT"
else
    vram_preflight || exit 1   # refuses if short; relaunch with CLEAR=1 to free registered tools
    clear_port "$LLM_PORT"
    echo "🚀 Starting llama-server (Q8_0, ctx $CTX)..."
    setsid nohup "$LLAMA_SERVER" -m "$MODEL" --host 127.0.0.1 --port "$LLM_PORT" \
        -ngl 999 -c "$CTX" -np 1 -fa on --jinja --reasoning-format deepseek \
        --alias glb-3d-coder --no-webui \
        < /dev/null > "$LLM_LOG" 2>&1 &
    register_tool $!          # the GPU holder — CLEAR=1 / eviction stops this one
    if ! wait_for_port "$LLM_PORT" 120; then
        echo "❌ llama-server not up in time — check $LLM_LOG"
        tail -30 "$LLM_LOG"
        exit 1
    fi
    for _ in $(seq 1 60); do   # port opens before the model finishes loading
        curl -s --max-time 2 "http://127.0.0.1:$LLM_PORT/health" | grep -q '"ok"' && break
        sleep 1
    done
fi

clear_port "$PORT"
echo "🚀 Starting $SERVICE_NAME UI..."
setsid nohup "$DRAGONSUITE_ROOT/$VENV/bin/python" "$APP" < /dev/null > "$LOG" 2>&1 &
echo "⏳ Waiting for UI..."
if wait_for_port "$PORT" 60; then
    echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
else
    echo "❌ UI not up in time — check $LOG"
    tail -30 "$LOG"
    exit 1
fi
