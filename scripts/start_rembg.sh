#!/bin/bash
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
# Launch Rembg Background Remover
# Port: 8012

set -e
cd /srv/containers/edq

echo "🐉 Starting Rembg Background Remover..."
echo "   Port: 8012"
echo "   Output: ~/ai_generated/rembg/"
echo ""

source venv_rembg/bin/activate
python scripts/rembg_gradio.py
