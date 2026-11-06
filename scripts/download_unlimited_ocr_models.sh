#!/bin/bash
# Pre-download Unlimited OCR 2 (baidu/Unlimited-OCR-2, 3.3B, ~6.7GB bf16) — run once before first launch.
# Skips the demo GIF, paper PDF and the custom SGLang wheel (this service uses the Transformers path).
set -e
cd /srv/containers/edq
source venv_unlimited_ocr/bin/activate

python3 << 'PYEOF'
import os
from huggingface_hub import snapshot_download

repo_id = "baidu/Unlimited-OCR-2"
local_dir = "/srv/containers/edq/models/unlimited-ocr-2"
os.makedirs(local_dir, exist_ok=True)
print(f"Downloading {repo_id} -> {local_dir}")
snapshot_download(
    repo_id=repo_id,
    local_dir=local_dir,
    ignore_patterns=["assets/*", "*.pdf", "wheel/*", ".gitattributes"],
)
print("Done. Launch with: bash scripts/start_unlimited_ocr.sh")
PYEOF
