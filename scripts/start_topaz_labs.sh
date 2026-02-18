#!/bin/bash

echo "🎨 Starting Topaz Labs AI Enhancement..."

# Check for API key
if ! grep -q "TOPAZ_API_KEY" /srv/containers/edq/.env 2>/dev/null; then
    echo "❌ TOPAZ_API_KEY not found in .env"
    echo "Get your API key from: https://developer.topazlabs.com/"
    exit 1
fi

# Activate dedicated Gradio venv
source /srv/containers/edq/venv_topaz_gradio/bin/activate

# Launch Gradio interface
echo "✓ Launching Topaz Labs web interface..."
echo "📍 Access at: http://192.168.7.226:8019"
echo ""

python /srv/containers/edq/scripts/topaz_labs_gradio.py
