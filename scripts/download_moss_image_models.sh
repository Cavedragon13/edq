#!/bin/bash
# Pre-download MOSS-Image models (run once before first launch)
# Base + SFT, ~27GB each. Each bundle is a complete diffusers folder
# (transformer, text_encoder, vae, tokenizer, scheduler + pipeline_moss_image.py).
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh
export HF_HOME="${HF_HOME:-/home/edq/.cache/huggingface}"

venv_py="/srv/containers/edq/venv_moss_image/bin/python"

"$venv_py" - << 'PYEOF'
import os
from huggingface_hub import snapshot_download

ROOT = "/srv/containers/edq/models/moss-image"
MODELS = [
    ("OpenMOSS-Team/MOSS-Image-SFT", f"{ROOT}/MOSS-Image-SFT"),
    ("OpenMOSS-Team/MOSS-Image-Base", f"{ROOT}/MOSS-Image-Base"),
]

for repo_id, local_dir in MODELS:
    os.makedirs(local_dir, exist_ok=True)
    print(f"Downloading {repo_id} -> {local_dir}", flush=True)
    snapshot_download(repo_id=repo_id, local_dir=local_dir)
    print("  done", flush=True)
print("All models ready. Launch with: bash scripts/start_moss_image.sh")
PYEOF
