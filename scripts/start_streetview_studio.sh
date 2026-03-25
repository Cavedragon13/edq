#!/bin/bash
# start_streetview_studio.sh — Street View Studio (port 8040)
# Fetch + AI-transform Google Street View images via FLUX.1-schnell (local, Apache 2.0)
set -e

VENV="/srv/containers/edq/venv_flux2"
SCRIPT="/srv/containers/edq/scripts/streetview_studio_gradio.py"
MODEL_DIR="/srv/containers/edq/models/flux1-schnell"

# Model check — fail fast before wasting time
if [ ! -f "$MODEL_DIR/model_index.json" ]; then
    echo "❌ FLUX.1-schnell not found at $MODEL_DIR"
    echo "   Run first: bash scripts/download_flux1_schnell.sh"
    exit 1
fi

# shellcheck source=/dev/null
source "$VENV/bin/activate"

echo "🗺️  Street View Studio"
echo "======================"
echo "Local:  http://localhost:8040"
echo "LAN:    http://192.168.7.226:8040"
echo ""
echo "Press Ctrl+C to stop"
echo ""

export PYTORCH_ALLOC_CONF=expandable_segments:True

exec python3 "$SCRIPT"
