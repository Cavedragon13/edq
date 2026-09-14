#!/bin/bash
# AuK — Tencent 1.5B speech generation + editing (Tencent-Hunyuan/AuK)
# Port: 8065
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

# Honest footprint. Upstream measured 16.75-16.98 GiB peak on an A800 with
# --cpu_offload (24.8-25.0 GiB without); the real peak on this 16 GB card is
# measured at first launch and recorded in docs/venvs.md. Lazy-loaded: the
# port comes up in seconds, the engine loads on the first request.
TOOL_NAME="auk"
REQ_VRAM_MIB=14000
REQ_RAM_MIB=16000
source scripts/vram_guard.sh

SERVICE_NAME="AuK"
PORT=8065
VENV="venv_auk"
APP_DIR="$DRAGONSUITE_ROOT/projects/AuK"
MODELS="$DRAGONSUITE_ROOT/models/auk"
SCRIPT="/srv/containers/edq/scripts/auk_gradio.py"
LOG_FILE="/tmp/auk.log"
# AUK_VARIANT=base (default) | flash | both. Both engines resident = ~2x VRAM,
# so only one is exposed unless explicitly asked for.
VARIANT="${AUK_VARIANT:-base}"

service_header "$SERVICE_NAME" "$PORT"

if [ ! -d "$APP_DIR/src/auk" ]; then
    echo "❌ Project not found: $APP_DIR  (git clone https://github.com/Tencent-Hunyuan/AuK.git projects/AuK)"
    exit 1
fi
if [ ! -f "$MODELS/AuK/auk_base.safetensors" ] || [ ! -d "$MODELS/Qwen2.5-Omni-3B" ]; then
    echo "❌ Models not found under $MODELS — run: bash scripts/download_auk_models.sh"
    exit 1
fi

vram_preflight || exit 1
clear_port "$PORT"
activate_venv "$VENV"
set_pytorch_env

mkdir -p "$HOME/ai_generated/auk"

ARGS=(--qwen_path "$MODELS/Qwen2.5-Omni-3B" --dtype bf16 --cpu_offload --host 0.0.0.0 --port "$PORT")
case "$VARIANT" in
    base)  ARGS+=(--base_ckpt "$MODELS/AuK/auk_base.safetensors" --base_config "$MODELS/AuK/config.yaml" --base_device cuda:0) ;;
    flash) ARGS+=(--flash_ckpt "$MODELS/AuK-Flash/auk_flash.safetensors" --flash_config "$MODELS/AuK-Flash/config.yaml" --flash_device cuda:0) ;;
    both)  ARGS+=(--base_ckpt "$MODELS/AuK/auk_base.safetensors" --base_config "$MODELS/AuK/config.yaml" --base_device cuda:0 \
                  --flash_ckpt "$MODELS/AuK-Flash/auk_flash.safetensors" --flash_config "$MODELS/AuK-Flash/config.yaml" --flash_device cuda:0) ;;
    *) echo "❌ AUK_VARIANT must be base|flash|both"; exit 1 ;;
esac

echo "🚀 Starting $SERVICE_NAME (variant: $VARIANT)..."
if pgrep -f "auk_gradio[.]py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    # cwd = repo so the vendor demo's relative assets/demo-input-audio examples resolve
    cd "$APP_DIR"
    nohup python "$SCRIPT" "${ARGS[@]}" > "$LOG_FILE" 2>&1 &
    register_tool $!
    echo "⏳ Waiting for service (log: $LOG_FILE)..."
    if wait_for_port "$PORT" 120; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT  (engine loads on first request)"
    else
        echo "❌ Service did not start in time — check $LOG_FILE"
        tail -15 "$LOG_FILE"
        exit 1
    fi
fi
