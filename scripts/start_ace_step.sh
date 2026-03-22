#!/bin/bash
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
# ACE-Step 1.5 Music Generation Launcher
# Dragonsuite Integration - Port 8016

set -e

cd /srv/containers/edq/projects/ACE-Step-1.5

echo "🎵 Starting ACE-Step 1.5 Music Generation..."
echo "📍 Port: 8021"
echo "🌐 LAN Access: http://192.168.7.226:8021"
echo ""

# Launch ACE-Step with custom settings for Dragonsuite
uv run acestep \
  --port 8021 \
  --server-name 0.0.0.0 \
  --language en \
  --config_path acestep-v15-turbo \
  --lm_model_path acestep-5Hz-lm-1.7B \
  --init_service true
