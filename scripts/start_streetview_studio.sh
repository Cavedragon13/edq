#!/bin/bash
# start_streetview_studio.sh — Street View Studio (port 8040)
# Fetch + AI-transform Google Street View images via FLUX.1 Kontext
set -e

VENV="/srv/containers/edq/venv_streetview"
SCRIPT="/srv/containers/edq/scripts/streetview_studio_gradio.py"

# Create venv on first run (no GPU packages — installs in ~30s)
if [ ! -f "$VENV/bin/activate" ]; then
    echo "⏳ First run: creating venv_streetview (lightweight, ~30s)..."
    python3 -m venv "$VENV"
    source "$VENV/bin/activate"
    pip install -q --upgrade pip
    pip install -q gradio gradio_client requests Pillow python-dotenv
    echo "✅ venv_streetview ready"
else
    source "$VENV/bin/activate"
fi

echo "🗺️  Starting Street View Studio on port 8040..."
exec python3 "$SCRIPT"
