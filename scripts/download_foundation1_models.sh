#!/bin/bash
set -e
source /srv/containers/edq/venv_foundation1/bin/activate

echo "Downloading Foundation-1 model..."
python << 'PYEOF'
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id="RoyalCities/Foundation-1",
    local_dir="/srv/containers/edq/projects/foundation-1/models",
    ignore_patterns=["*.md", ".gitattributes"]
)
print("Download complete.")
PYEOF
