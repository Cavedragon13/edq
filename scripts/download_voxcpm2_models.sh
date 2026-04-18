#!/bin/bash
set -e
source /srv/containers/edq/venv_voxcpm2/bin/activate
export HF_HOME=/srv/containers/edq/cache_huggingface

echo "Downloading VoxCPM2 to HF cache..."
python3 << 'PYEOF'
from huggingface_hub import snapshot_download
snapshot_download(repo_id="openbmb/VoxCPM2", ignore_patterns=["*.md", "*.txt"])
print("VoxCPM2 download complete.")
PYEOF
