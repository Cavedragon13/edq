#!/bin/bash
# Pre-download all TripoSplat Studio models (run once before first launch).
# Weights live in models/triposplat; projects/TripoSplat/ckpts and the Pinokio
# app's app/ckpts are symlinks to it (one copy, ~4.2GB).
set -e
cd /srv/containers/edq
source venv_triposplat/bin/activate

python3 - <<'PYEOF'
from huggingface_hub import snapshot_download

# Repo verified 2026-09-24: https://huggingface.co/VAST-AI/TripoSplat
path = snapshot_download(
    repo_id="VAST-AI/TripoSplat",
    local_dir="/srv/containers/edq/models/triposplat",
    ignore_patterns=["*.md", ".gitattributes"],
)
print(f"TripoSplat weights ready in {path}")
print("Launch with: bash scripts/start_triposplat.sh")
PYEOF
