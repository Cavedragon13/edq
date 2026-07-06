#!/usr/bin/env bash
set -euo pipefail

cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

TOOL_NAME="krea2-turbo"
REQ_VRAM_MIB=11000
REQ_RAM_MIB=10000
source scripts/vram_guard.sh

SERVICE_NAME="Krea 2 Turbo"
PORT="${KREA2_PORT:-8062}"
APP_DIR="$DRAGONSUITE_ROOT/krea2"

export KREA2_HOME="$APP_DIR"
export KREA2_HOST="${KREA2_HOST:-0.0.0.0}"
export KREA2_PORT="$PORT"
export KREA2_SD_CLI="${KREA2_SD_CLI:-$APP_DIR/src/stable-diffusion.cpp/build-cuda/bin/sd-cli}"
export KREA2_OUTPUT_DIR="${KREA2_OUTPUT_DIR:-/home/edq/ai_generated/krea2}"
export KREA2_LOG_DIR="${KREA2_LOG_DIR:-$APP_DIR/logs}"
export KREA2_LORA_DIR="${KREA2_LORA_DIR:-$APP_DIR/loras}"
export KREA2_BACKEND="${KREA2_BACKEND:-}"
export KREA2_DIFFUSION_MODEL="${KREA2_DIFFUSION_MODEL:-$APP_DIR/models/TURBO/Krea-2-Turbo-Q4_K_M.gguf}"
export KREA2_LLM_MODEL="${KREA2_LLM_MODEL:-$APP_DIR/models/Qwen3VL-4B-Instruct-Q4_K_M.gguf}"
export KREA2_VAE_MODEL="${KREA2_VAE_MODEL:-$APP_DIR/models/split_files/vae/wan_2.1_vae.safetensors}"

service_header "$SERVICE_NAME" "$PORT"

for required in "$KREA2_SD_CLI" "$KREA2_DIFFUSION_MODEL" "$KREA2_LLM_MODEL" "$KREA2_VAE_MODEL"; do
  if [ ! -f "$required" ]; then
    echo "Missing required Krea 2 file: $required"
    echo "Run the Krea 2 model download/build setup before launching."
    exit 1
  fi
done

mkdir -p "$KREA2_OUTPUT_DIR" "$KREA2_LOG_DIR" "$KREA2_LORA_DIR"
vram_preflight || exit 1
clear_port "$PORT"
activate_venv venv_dragonsuite

echo "Starting $SERVICE_NAME..."
nohup setsid bash -c 'exec python "$1"' _ "$APP_DIR/krea2_runner.py" > /tmp/krea2_cuda_runner.log 2>&1 &
register_tool $!

if wait_for_port "$PORT" 60; then
  echo "$SERVICE_NAME ready at http://192.168.7.226:$PORT"
else
  echo "Krea 2 runner did not start in time. Check /tmp/krea2_cuda_runner.log"
  tail -20 /tmp/krea2_cuda_runner.log
  exit 1
fi
