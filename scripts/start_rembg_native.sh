#!/bin/bash
# Rembg - Native UI (port 8012)
set -e
cd /srv/containers/edq

echo "🐉 Rembg (native UI) - Background Remover"
echo "   Port:   8012"
echo "   Output: ~/ai_generated/rembg/"

source venv_rembg/bin/activate
pip install -q fastapi uvicorn python-multipart 2>/dev/null || true

exec python scripts/rembg_server.py
