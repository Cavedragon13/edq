#!/bin/bash
# Pre-download MiniMax Music 3 weights (run once before first launch)
# Repo: MiniMaxAI/MiniMax-Music3 (Apache-2.0) — ~20GB in bf16
# Safe to interrupt (Ctrl+C) and resume — huggingface_hub downloads are resumable.
set -e
cd /srv/containers/edq
source venv_minimax_music3/bin/activate

python3 << 'PYEOF'
from huggingface_hub import snapshot_download
from pathlib import Path

local_dir = Path("/srv/containers/edq/models/minimax-music3")
local_dir.mkdir(parents=True, exist_ok=True)

print("Downloading MiniMaxAI/MiniMax-Music3 (~20GB)...")
snapshot_download(
    repo_id="MiniMaxAI/MiniMax-Music3",
    local_dir=str(local_dir),
    ignore_patterns=["*.md", "*.txt", ".gitattributes", "assets/*", "figures/*"],
)
print("Done.")
PYEOF

deactivate

echo ""
echo "======================================"
echo "MiniMax Music 3 models ready."
echo "Location: /srv/containers/edq/models/minimax-music3"
echo "Next: bash scripts/start_minimax_music3.sh"
echo "======================================"
