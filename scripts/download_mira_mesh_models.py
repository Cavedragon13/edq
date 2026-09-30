"""Download the complete gated SAM3D checkpoint repository explicitly."""

import os
from pathlib import Path

from huggingface_hub import snapshot_download


os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
target = Path("/srv/containers/edq/models/mira-scene/stages/sam3d")
target.mkdir(parents=True, exist_ok=True)
print("Downloading facebook/sam-3d-objects ->", target, flush=True)
snapshot_download(
    repo_id="facebook/sam-3d-objects",
    repo_type="model",
    local_dir=str(target),
)
print("Mira SAM3D checkpoint repository is ready.", flush=True)
