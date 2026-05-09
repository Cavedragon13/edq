#!/bin/bash
# Hunyuan3D-2 — Image to 3D mesh generation (Tencent)
# Port: 8007
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="Hunyuan3D-2"
PORT=8007
VENV="venv_hunyuan3d"
HUNYUAN3D_DIR="/srv/containers/edq/projects/hunyuan3d"
OUTPUT_DIR="$HOME/ai_generated/hunyuan3d"

HF_CACHE="${HF_HOME:-$HOME/.cache/huggingface}/hub"
SHAPE_MODEL_CACHE="$HF_CACHE/models--tencent--Hunyuan3D-2mini"
TEXGEN_MODEL_CACHE="$HF_CACHE/models--tencent--Hunyuan3D-2"

service_header "$SERVICE_NAME" "$PORT"
gpu_preflight "$PORT"
activate_venv "$VENV"
set_pytorch_env

# Model check — fail fast before wasting time
if [ ! -d "$SHAPE_MODEL_CACHE" ] || [ ! -d "$TEXGEN_MODEL_CACHE" ]; then
    echo "❌ Hunyuan3D-2 models not found in HuggingFace cache."
    echo "   Run the download script first:"
    echo "   bash scripts/download_hunyuan3d_models.sh"
    exit 1
fi
echo "✓ Models found"
echo ""

mkdir -p "$OUTPUT_DIR"
export HUNYUAN3D_OUTPUT_DIR="$OUTPUT_DIR"
export NUMBA_CACHE_DIR="/tmp/numba_cache_hunyuan3d"
mkdir -p "$NUMBA_CACHE_DIR"

echo "🚀 Starting $SERVICE_NAME..."
echo "   Output saves to: $OUTPUT_DIR"
echo ""

if pgrep -f "hunyuan3d.*gradio_app\.py\|gradio_app\.py.*hunyuan3d\|projects/hunyuan3d" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    cd "$HUNYUAN3D_DIR"
    nohup python gradio_app.py --host 0.0.0.0 --port "$PORT" --cache-path "$OUTPUT_DIR" \
        > /tmp/hunyuan3d.log 2>&1 &
    cd /srv/containers/edq
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 60; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Failed — check /tmp/hunyuan3d.log"
        tail -10 /tmp/hunyuan3d.log
        exit 1
    fi
fi
