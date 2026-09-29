#!/usr/bin/env bash
# Download the core Mira-Scene inference pipeline explicitly.
set -euo pipefail
cd /srv/containers/edq
source venv_supra2_img/bin/activate
export HF_HUB_DISABLE_XET=1

python3 - <<'PY'
from pathlib import Path
from huggingface_hub import snapshot_download

root = Path('/srv/containers/edq/models/mira-scene')
root.mkdir(parents=True, exist_ok=True)
print('Downloading Yang-Tian/Mira-Scene pipeline ->', root, flush=True)
snapshot_download(
    repo_id='Yang-Tian/Mira-Scene',
    local_dir=str(root),
    allow_patterns=['pipeline/*'],
)
print('Mira-Scene core pipeline is ready.', flush=True)
PY
