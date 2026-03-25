#!/bin/bash
# Download FLUX.1-schnell (Apache 2.0 — commercial use OK)
# ~24GB download, resumable via snapshot_download
set -e

VENV="/srv/containers/edq/venv_flux2"
MODEL_DIR="/srv/containers/edq/models/flux1-schnell"

echo "📥 FLUX.1-schnell downloader"
echo "=============================="
echo "License: Apache 2.0 (commercial use permitted)"
echo "Target:  $MODEL_DIR"
echo "Size:    ~24GB"
echo ""

if [ -d "$MODEL_DIR" ] && [ -f "$MODEL_DIR/model_index.json" ]; then
    echo "✅ Already downloaded at $MODEL_DIR"
    exit 0
fi

source "$VENV/bin/activate"

python3 << 'PYEOF'
from huggingface_hub import snapshot_download
import os

target = "/srv/containers/edq/models/flux1-schnell"
os.makedirs(target, exist_ok=True)

print("⏳ Downloading FLUX.1-schnell (resumable)...")
snapshot_download(
    repo_id="black-forest-labs/FLUX.1-schnell",
    local_dir=target,
    ignore_patterns=["*.md"],
)
print(f"✅ Done → {target}")
PYEOF
