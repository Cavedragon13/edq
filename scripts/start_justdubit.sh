#!/bin/bash
set -e

echo "🎬 Starting JustDubit..."

cd /srv/containers/edq

# Set CUDA memory config
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

echo "✓ Launching JustDubit Gradio UI on port 8022..."
echo "⚠️  Note: Model checkpoints need to be downloaded first"

python scripts/justdubit_gradio.py
