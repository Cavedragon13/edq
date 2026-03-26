#!/bin/bash
# start_dragonglass.sh — DragonGlass (port 8040)
# Street View scout + FLUX.1-schnell AI transform
set -e

VENV="/srv/containers/edq/venv_flux2"
SCRIPT="/srv/containers/edq/scripts/dragonglass.py"
MODEL_DIR="/srv/containers/edq/models/flux1-schnell"

if [ ! -f "$MODEL_DIR/model_index.json" ]; then
    echo "❌ FLUX.1-schnell not found at $MODEL_DIR"
    echo "   Run first: bash scripts/download_flux1_schnell.sh"
    exit 1
fi

source "$VENV/bin/activate"

echo "◆  DragonGlass"
echo "==============="
echo "Local:  http://localhost:8040"
echo "LAN:    http://192.168.7.226:8040"
echo ""
echo "Press Ctrl+C to stop"
echo ""

export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

exec python3 "$SCRIPT"
