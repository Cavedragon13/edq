#!/bin/bash
# Dolphin Vision 7B - Native UI (port 8025)
# /analyze JSON endpoint preserved for Dragonsight 4 integration.
set -e
cd /srv/containers/edq
VENV="/srv/containers/edq/venv_dolphin_vision"

echo "🐬 Dolphin Vision (native UI)"
echo "   Port:   8025"
echo "   /analyze endpoint preserved for Dragonsight 4"

source "$VENV/bin/activate"
pip install -q fastapi uvicorn python-multipart 2>/dev/null || true
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
exec python scripts/dolphin_vision_server.py
