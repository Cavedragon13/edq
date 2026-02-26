#!/bin/bash
# Real-ESRGAN - Native UI (port 8010)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/venv_realesrgan"

echo "🔍 Real-ESRGAN (native UI)"
echo "   Port:   8010"
echo "   Access: http://192.168.7.226:8010"

source "$VENV_DIR/bin/activate"
pip install -q fastapi uvicorn python-multipart 2>/dev/null || true

export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
cd "$PROJECT_DIR"
exec python scripts/realesrgan_server.py
