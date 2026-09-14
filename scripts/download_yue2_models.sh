#!/bin/bash
# Pre-download YuE2 models (run once before first launch). Never let the first
# launch pull these silently.
#
# Weights go into the shared HF hub cache (~/.cache/huggingface -> cache_huggingface)
# rather than a local_dir, because yue2's YuE2Pipeline.from_pretrained("m-a-p/...")
# resolves repos through the hub cache. Marketing audio/figures are skipped.
#
# Uses venv_dragonsuite's huggingface_hub so this can run while venv_yue2 is
# still being built; either venv works.
set -e
cd /srv/containers/edq
PY="/srv/containers/edq/venv_yue2/bin/python"
[ -x "$PY" ] && "$PY" -c "import huggingface_hub" 2>/dev/null || PY="/srv/containers/edq/venv_dragonsuite/bin/python"

"$PY" - <<'PYEOF'
from huggingface_hub import snapshot_download

REPOS = [
    "m-a-p/YuE2-3B",      # 7.3 GB AR-NAR backbone + tokenizer + inference wheel
    "m-a-p/YuE2-Vae",     # 0.5 GB default decoder (48 kHz stereo)
]
SKIP = ["assets/*", "*.pdf", "*.svg", "*.png", "*.mp3", ".gitattributes"]

for repo in REPOS:
    print(f"Downloading {repo}")
    path = snapshot_download(repo_id=repo, ignore_patterns=SKIP)
    print(f"  ready at {path}")
print("All YuE2 models ready. Launch with: bash scripts/start_yue2.sh")
PYEOF
