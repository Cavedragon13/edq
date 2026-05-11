#!/bin/bash
# Pre-download HiDream-O1-Image-Dev model weights (run once before first launch)
set -e
cd /srv/containers/edq
source venv_hidream_o1/bin/activate

python3 << 'PYEOF'
import os
from huggingface_hub import snapshot_download

MODELS = [
    ("HiDream-ai/HiDream-O1-Image-Dev", "/srv/containers/edq/models/hidream-o1-dev"),
]

for repo_id, local_dir in MODELS:
    os.makedirs(local_dir, exist_ok=True)
    print(f"Downloading {repo_id} → {local_dir}")
    snapshot_download(
        repo_id=repo_id,
        local_dir=local_dir,
        ignore_patterns=["*.md", "*.txt", ".gitattributes"],
    )
    print(f"  ✓ done")

print("\nAll models ready. Launch with: bash scripts/start_hidream_o1.sh")
PYEOF
