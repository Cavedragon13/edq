#!/bin/bash
# OmniVoice - upstream Gradio demo launcher
# Zero-shot TTS + Voice Cloning + Voice Design
# Port 8045, LAN accessible
set -euo pipefail
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="OmniVoice"
PORT=8045
VENV="venv_omnivoice"
PROJECT_DIR="$DRAGONSUITE_ROOT/projects/OmniVoice"
VENV_DIR="$DRAGONSUITE_ROOT/$VENV"
LOG_FILE="/tmp/omnivoice.log"
REPO_URL="https://github.com/k2-fsa/OmniVoice.git"
OUTPUT_DIR="$HOME/ai_generated/omnivoice"

safe_gpu_preflight() {
    local port="$1"
    local freed=0
    echo "🔧 Pre-flight checks..."
    vram_status || true
    evict_lmstudio || true

    while IFS=, read -r pid vram; do
        pid="${pid// /}"
        vram="${vram// /}"
        [ -n "$pid" ] || continue
        [[ "$pid" =~ ^[0-9]+$ ]] || continue
        [ "$pid" = "$$" ] && continue

        cmdline=$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)
        [[ "$cmdline" == *python* ]] || continue
        [[ "$cmdline" == *dragonsuite_server* ]] && continue
        [[ "$cmdline" == *ollama* ]] && continue

        echo "  ⚡ Evicting PID $pid (${vram} MiB VRAM): $cmdline"
        kill -TERM "$pid" 2>/dev/null || true
        freed=1
    done < <(nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader,nounits 2>/dev/null || true)

    if [ "$freed" -eq 1 ]; then
        echo "  ⏳ Waiting for VRAM to clear..."
        sleep 3
    fi

    clear_port "$port"
    echo "✓ VRAM after eviction:"
    vram_status || true
    echo ""
}

service_header "$SERVICE_NAME" "$PORT"
safe_gpu_preflight "$PORT"

if [ ! -d "$PROJECT_DIR/.git" ]; then
    echo "📥 Cloning OmniVoice..."
    git clone "$REPO_URL" "$PROJECT_DIR"
fi

if [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo "🐍 Creating venv: $VENV"
    python3 -m venv "$VENV_DIR"
fi

activate_venv "$VENV"

ensure_python_pkg() {
    local import_name="$1"
    shift
    if ! python -c "import ${import_name}" >/dev/null 2>&1; then
        pip install "$@"
    fi
}

echo "📦 Ensuring Python packaging tools..."
pip install --upgrade pip setuptools wheel >/dev/null

if ! python - <<'PY' >/dev/null 2>&1
import torch, torchaudio
assert torch.version.cuda == "12.8"
PY
then
    echo "📦 Installing PyTorch CUDA 12.8 stack..."
    pip install --index-url https://download.pytorch.org/whl/cu128 torch==2.10.0 torchaudio==2.10.0
fi

echo "📦 Ensuring OmniVoice runtime dependencies..."
ensure_python_pkg transformers 'transformers>=4.53.0'
ensure_python_pkg accelerate accelerate
ensure_python_pkg gradio gradio
ensure_python_pkg pydub pydub
ensure_python_pkg tensorboardX tensorboardX
ensure_python_pkg webdataset webdataset
ensure_python_pkg soundfile soundfile
ensure_python_pkg sentencepiece sentencepiece
ensure_python_pkg huggingface_hub huggingface_hub

if ! command -v omnivoice-demo >/dev/null 2>&1 || ! python -c "import omnivoice" >/dev/null 2>&1; then
    echo "📦 Installing OmniVoice package from source..."
    (cd "$PROJECT_DIR" && pip install --no-deps -e .)
fi

set_pytorch_env
mkdir -p "$OUTPUT_DIR"

export HF_HUB_DISABLE_TELEMETRY=1
export GRADIO_SERVER_NAME="0.0.0.0"
export GRADIO_SERVER_PORT="$PORT"

echo "🚀 Starting $SERVICE_NAME..."
if pgrep -f "omnivoice-demo.*--port $PORT" >/dev/null; then
    echo "✓ Already running on port $PORT"
else
    cd "$PROJECT_DIR"
    nohup "$VENV_DIR/bin/omnivoice-demo" --ip 0.0.0.0 --port "$PORT" > "$LOG_FILE" 2>&1 &
    echo "⏳ Waiting for service and model load..."
    if wait_for_port "$PORT" 420; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Service did not start in time — check $LOG_FILE"
        tail -40 "$LOG_FILE" || true
        exit 1
    fi
fi
