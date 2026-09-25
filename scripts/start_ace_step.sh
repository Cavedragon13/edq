#!/bin/bash
# ACE-Step 1.5 XL Music Generation
# Port: 8021
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

# Honest footprint — measured 2026-09-24 (see docs/venvs.md).
TOOL_NAME="ace-step"
REQ_VRAM_MIB=13000
REQ_RAM_MIB=8000
source scripts/vram_guard.sh

SERVICE_NAME="ACE-Step 1.5 XL"
PORT=8021
ACE_HOME="$DRAGONSUITE_ROOT/projects/ACE-Step-1.5-xl"
ACE_CHECKPOINTS_DIR="$ACE_HOME/checkpoints"

service_header "$SERVICE_NAME" "$PORT"
if [ ! -d "$ACE_HOME/.git" ] || [ ! -x "$ACE_HOME/.venv/bin/python" ]; then
    echo "❌ ACE-Step project/venv not found at $ACE_HOME"
    echo "   git clone https://github.com/ACE-Step/ACE-Step-1.5.git projects/ACE-Step-1.5-xl && (cd projects/ACE-Step-1.5-xl && uv sync)"
    exit 1
fi
if [ ! -d "$ACE_CHECKPOINTS_DIR/acestep-v15-xl-turbo" ] || [ ! -d "$ACE_CHECKPOINTS_DIR/acestep-5Hz-lm-1.7B" ]; then
    echo "❌ ACE-Step XL checkpoints not found at $ACE_CHECKPOINTS_DIR"
    echo "   Run: bash scripts/download_ace_step_models.sh"
    exit 1
fi

export ACESTEP_CHECKPOINTS_DIR="$ACE_CHECKPOINTS_DIR"
# Upstream's "legacy NVIDIA" probe can force-reinstall torch 2.5.1+cu121, which
# has no Blackwell (sm_120) kernels. Never let it run here.
export ACESTEP_SKIP_LEGACY_TORCH_FIX=true
# CHECK_UPDATE=false disables the interactive update prompt that blocks headless launches.
export CHECK_UPDATE=false

vram_preflight || exit 1
set_pytorch_env

echo "🚀 Starting $SERVICE_NAME..."
if ss -tlnp | grep -q ":${PORT} "; then
    echo "✓ Already running on port $PORT"
else
    # Upstream launches with `uv run --no-sync`, so dependencies added by an
    # update would never install. Sync first (a no-op in ~1s when current).
    echo "📦 Syncing dependencies (uv sync)..."
    UV="$(command -v uv || echo /home/edq/.local/bin/uv)"   # dashboard's PATH may lack ~/.local/bin
    (cd "$ACE_HOME" && "$UV" sync --quiet)
    nohup bash -c "cd '$ACE_HOME' && bash ./start_gradio_ui.sh" > /tmp/ace_step_xl.log 2>&1 &
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 1800; then
        # The launch is a bash → uv → python chain; register the python process
        # that owns the port, so CLEAR=1 frees the VRAM rather than a wrapper.
        server_pid=$(ss -tlnp "sport = :$PORT" | grep -oP 'pid=\K[0-9]+' | head -1)
        [ -n "$server_pid" ] && register_tool "$server_pid"
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Service did not start in time — check /tmp/ace_step_xl.log"
        tail -10 /tmp/ace_step_xl.log
        exit 1
    fi
fi
