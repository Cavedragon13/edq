#!/bin/bash
# Download LavaSR models from HuggingFace
# Run this ONCE before first use. Resumable and idempotent.
# Model: ~50MB, Apache-2.0 license

set -e

VENV="/srv/containers/edq/venv_lavasr"

if [ ! -d "$VENV" ]; then
    echo "ERROR: venv_lavasr not found. Run setup first."
    exit 1
fi

source "$VENV/bin/activate"

echo
echo "LavaSR Model Download"
echo "====================="
echo "  Repo:  YatharthS/LavaSR"
echo "  Size:  ~50MB"
echo

python3 << 'PYEOF'
from huggingface_hub import snapshot_download
import os

print("Downloading YatharthS/LavaSR...")
path = snapshot_download(
    repo_id="YatharthS/LavaSR",
    cache_dir=os.path.expanduser("~/.cache/huggingface/hub")
)
print(f"✓ Downloaded to: {path}")
PYEOF

echo
echo "✓ LavaSR models ready."
echo "You can now start the service: bash scripts/start_lavasr.sh"
