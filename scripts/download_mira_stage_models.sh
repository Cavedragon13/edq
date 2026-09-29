#!/usr/bin/env bash
set -euo pipefail

ROOT=/srv/containers/edq
PY="$ROOT/venv_supra2_img/bin/python"
export HF_HUB_DISABLE_XET=1
export MIRA_STAGE_DOWNLOAD_MODE="${1:-all}"

"$PY" - <<'PY'
import os
from pathlib import Path
from huggingface_hub import hf_hub_download

root = Path('/srv/containers/edq/models/mira-scene/stages')
depth_downloads = [
    ('gangweix/Pixel-Perfect-Depth', 'ppd.pth', root / 'ppd'),
    ('Ruicheng/moge-2-vitl-normal', 'model.pt', root / 'ppd' / 'moge2'),
    ('depth-anything/Depth-Anything-V2-Large', 'depth_anything_v2_vitl.pth', root / 'ppd'),
]
sam3_download = ('facebook/sam3', 'sam3.pt', root / 'sam3')
for repo_id, filename, local_dir in depth_downloads:
    local_dir.mkdir(parents=True, exist_ok=True)
    print(f'Downloading {repo_id}/{filename} -> {local_dir}', flush=True)
    hf_hub_download(repo_id=repo_id, filename=filename, local_dir=str(local_dir))
    print(f'  ready: {local_dir / filename}', flush=True)
if os.environ.get('MIRA_STAGE_DOWNLOAD_MODE', 'all') != 'depth-only':
    repo_id, filename, local_dir = sam3_download
    local_dir.mkdir(parents=True, exist_ok=True)
    print(f'Downloading {repo_id}/{filename} -> {local_dir}', flush=True)
    hf_hub_download(repo_id=repo_id, filename=filename, local_dir=str(local_dir))
    print(f'  ready: {local_dir / filename}', flush=True)
print('Mira segmentation and depth checkpoints are ready.')
PY
