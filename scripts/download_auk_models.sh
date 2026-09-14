#!/bin/bash
# Pre-download AuK models (run once before first launch). Never let the first
# launch pull these silently.
#
# Layout matches the upstream README's expected ckpts/ tree:
#   models/auk/AuK/             base model  (6.1 GB DiT + VAE)
#   models/auk/AuK-Flash/       4-step distilled variant
#   models/auk/Qwen2.5-Omni-3B/ MLLM encoder (loaded separately at runtime)
set -e
cd /srv/containers/edq
PY="/srv/containers/edq/venv_auk/bin/python"
[ -x "$PY" ] && "$PY" -c "import huggingface_hub" 2>/dev/null || PY="/srv/containers/edq/venv_dragonsuite/bin/python"

"$PY" - <<'PYEOF'
import os
from huggingface_hub import snapshot_download

MODELS = [
    ("tencent/AuK",          "/srv/containers/edq/models/auk/AuK"),
    ("tencent/AuK-Flash",    "/srv/containers/edq/models/auk/AuK-Flash"),
    ("Qwen/Qwen2.5-Omni-3B", "/srv/containers/edq/models/auk/Qwen2.5-Omni-3B"),
]
for repo_id, local_dir in MODELS:
    os.makedirs(local_dir, exist_ok=True)
    print(f"Downloading {repo_id} -> {local_dir}")
    snapshot_download(repo_id=repo_id, local_dir=local_dir,
                      ignore_patterns=["assets/*", "*.png", "*.md", ".gitattributes"])
    print("  done")
print("All AuK models ready. Launch with: bash scripts/start_auk.sh")
PYEOF
