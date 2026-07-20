#!/bin/bash
# Pre-download Lucida model weights (run once before first launch)
# Downloads egeorcun/lucida (BiRefNet fine-tune, MIT) into the standard HF cache.
set -e
cd /srv/containers/edq/projects/lucida
source .venv/bin/activate

python3 << 'PYEOF'
from huggingface_hub import snapshot_download

print("Downloading egeorcun/lucida (BiRefNet fine-tune, ~850MB)")
snapshot_download(
    repo_id="egeorcun/lucida",
    ignore_patterns=[".gitattributes"],
)
print("Done. Launch with: bash scripts/start_lucida.sh")
PYEOF
