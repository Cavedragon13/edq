#!/bin/bash
set -e

echo "🎤 Starting SoulX-Singer..."

cd /srv/containers/edq/projects/SoulX-Singer

# Activate venv
source /srv/containers/edq/venv_soulxsinger/bin/activate

# Set CUDA memory config for Blackwell GPU
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

# Launch webui
echo "✓ Launching SoulX-Singer WebUI on port 8023..."
python webui.py --port 8023

