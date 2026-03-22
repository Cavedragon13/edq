#!/bin/bash
set -e

echo "🎭 Starting FaceFusion - Face Swap & Manipulation..."

# Activate venv
source /srv/containers/edq/venv_facefusion/bin/activate

# Navigate to FaceFusion directory
cd /srv/containers/edq/projects/facefusion

# Check if Ollama is running (optional, for best results)
if curl -s http://127.0.0.1:11434/api/tags > /dev/null 2>&1; then
    echo "✓ Ollama detected (can be used for face analysis)"
fi

# Launch FaceFusion with Gradio interface
echo "✓ Launching FaceFusion web interface..."
echo "📍 Access at: http://192.168.7.226:8017"
echo ""

# Set Gradio server config via environment variables
export GRADIO_SERVER_NAME=0.0.0.0
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export GRADIO_SERVER_PORT=8017

python facefusion.py run \
    --execution-providers cuda \
    --ui-layouts webcam benchmark
