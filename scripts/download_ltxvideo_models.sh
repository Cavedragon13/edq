#!/bin/bash
# download_ltxvideo_models.sh — Download LTX-Video-0.9.7-distilled + spatial upscaler
# Run ONCE before first launch. Idempotent — safe to re-run.
set -e

VENV="/srv/containers/edq/venv_ltxvideo"
MODEL_DIR="/srv/containers/edq/models/ltxvideo"
UPSCALER_DIR="/srv/containers/edq/models/ltxvideo_upscaler"

if [ ! -f "$VENV/bin/activate" ]; then
    echo "❌ venv_ltxvideo not found. Run: python3 -m venv $VENV first."
    exit 1
fi

source "$VENV/bin/activate"

python3 << 'PYEOF'
import os
from huggingface_hub import snapshot_download

for repo_id, local_dir in [
    ("Lightricks/LTX-Video-0.9.7-distilled", "/srv/containers/edq/models/ltxvideo"),
    ("Lightricks/ltxv-spatial-upscaler-0.9.7", "/srv/containers/edq/models/ltxvideo_upscaler"),
]:
    os.makedirs(local_dir, exist_ok=True)
    print(f"Downloading {repo_id}...")
    snapshot_download(
        repo_id=repo_id,
        local_dir=local_dir,
        ignore_patterns=["*.md", "*.txt", ".gitattributes"],
    )
    print(f"  ✅ → {local_dir}")

print("\n✅ All models downloaded.")
PYEOF
