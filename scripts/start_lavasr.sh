#!/bin/bash
# Start LavaSR Speech Enhancement (port 8034)
set -e

cd /srv/containers/edq

VENV="venv_lavasr"
SCRIPT="scripts/lavasr_server.py"
MODEL_CACHE="$HOME/.cache/huggingface/hub/models--YatharthS--LavaSR"

# Check model downloaded
if [ ! -d "$MODEL_CACHE" ]; then
    echo "❌ LavaSR models not found at: $MODEL_CACHE"
    echo ""
    echo "   Run the download script first:"
    echo "   bash scripts/download_lavasr_models.sh"
    echo ""
    exit 1
fi

source "$VENV/bin/activate"
exec python3 "$SCRIPT"
