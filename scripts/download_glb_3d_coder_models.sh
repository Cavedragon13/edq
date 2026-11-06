#!/bin/bash
# Pre-download CCORE GLB-3D-Coder (ccore/Qwen3.5-4B-GLB-3D-Coder) — run once before first launch.
# Only the Q8_0 GGUF (4.5GB, the quant used for the author's evaluation) is needed; llama-server runs it.
# NOTE: the author re-uploaded weights on 2026-11-05 under the same filenames. Re-run with FORCE=1
# if the card announces another refresh.
set -e
cd /srv/containers/edq
source venv_glb_3d_coder/bin/activate

python3 << 'PYEOF'
import os
from huggingface_hub import hf_hub_download

repo_id = "ccore/Qwen3.5-4B-GLB-3D-Coder"
local_dir = "/srv/containers/edq/models/glb-3d-coder"
os.makedirs(local_dir, exist_ok=True)
for name in ["Qwen3.5-4B-GLB-3D-Coder-Q8_0.gguf", "README.md", "LICENSE"]:
    print(f"Downloading {repo_id}/{name}")
    hf_hub_download(repo_id=repo_id, filename=name, local_dir=local_dir,
                    force_download=os.environ.get("FORCE") == "1")
print("Done. Launch with: bash scripts/start_glb_3d_coder.sh")
PYEOF
