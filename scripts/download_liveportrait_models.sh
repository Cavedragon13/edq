#!/bin/bash
# Pre-download LivePortrait's pretrained weights (humans + animals base models,
# retargeting modules, InsightFace detector) into projects/LivePortrait/pretrained_weights.
# Repo verified against projects/LivePortrait/readme.md (section "Download pretrained weights"),
# 2026-10-17: KlingTeam/LivePortrait on HuggingFace Hub (~2GB).
set -e
cd /srv/containers/edq
LP_DIR="/srv/containers/edq/projects/LivePortrait"

venv_liveportrait/bin/python3 - <<'PYEOF'
from huggingface_hub import snapshot_download

snapshot_download(
    repo_id="KlingTeam/LivePortrait",
    local_dir="/srv/containers/edq/projects/LivePortrait/pretrained_weights",
    allow_patterns=["*"],
    ignore_patterns=["*.git*", "README.md", "docs/*"],
)
print("LivePortrait weights ready. Launch with: bash scripts/start_liveportrait.sh")
PYEOF
