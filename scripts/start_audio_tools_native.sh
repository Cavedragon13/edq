#!/bin/bash
# Audio Processing Suite - Native UI (port 8026)
set -e

SOULX_PROJECT="/srv/containers/edq/projects/SoulX-Singer"
VENV="/srv/containers/edq/venv_soulxsinger"
PREPROCESS_BASE="/srv/containers/edq/models/SoulX-Singer-Preprocess"

echo "🎵 Audio Processing Suite (native UI)"
echo "   Port: 8026"

if [ ! -d "$PREPROCESS_BASE/mel-band-roformer-karaoke" ]; then
  echo "❌ Audio processing models not found at: $PREPROCESS_BASE"
  echo ""
  echo "   Run the download script first:"
  echo "   bash scripts/download_soulxsinger_models.sh"
  echo ""
  exit 1
fi

source "$VENV/bin/activate"
pip install -q fastapi uvicorn python-multipart 2>/dev/null || true

export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
exec python /srv/containers/edq/scripts/audio_tools_server.py
