#!/bin/bash
# Pre-download HeartMuLa's checkpoints into projects/heartmula/ckpt before first
# launch. Repo ids verified against HfApi.list_models(author="HeartMuLa") and a
# sha256/size match against the already-installed decoder weights, 2026-10-17:
#   - HeartMuLa/HeartMuLa-oss-3B        -> ckpt/HeartMuLa-oss-3B   (generation model)
#   - HeartMuLa/HeartCodec-oss-20260123 -> ckpt/HeartCodec-oss     (decoder; this repo's
#     two safetensors shards are byte-equivalent to the merged single-file
#     model.safetensors already on disk here — "HeartCodec-oss" with no date/suffix
#     404s, it was renamed upstream)
set -e
cd /srv/containers/edq
CKPT_DIR="/srv/containers/edq/projects/heartmula/ckpt"

has_weights() {
    [ -f "$1/config.json" ] && ls "$1"/*.safetensors >/dev/null 2>&1
}

if has_weights "$CKPT_DIR/HeartMuLa-oss-3B" && has_weights "$CKPT_DIR/HeartCodec-oss"; then
    echo "✓ HeartMuLa checkpoints already present at $CKPT_DIR — skipping download."
    exit 0
fi

venv_heartmula/bin/python3 - <<PYEOF
from huggingface_hub import snapshot_download

REPOS = {
    "HeartMuLa/HeartMuLa-oss-3B": "$CKPT_DIR/HeartMuLa-oss-3B",
    "HeartMuLa/HeartCodec-oss-20260123": "$CKPT_DIR/HeartCodec-oss",
}
for repo_id, local_dir in REPOS.items():
    print(f"Downloading {repo_id} -> {local_dir}", flush=True)
    snapshot_download(repo_id=repo_id, local_dir=local_dir,
                       ignore_patterns=["*.git*"])
print("HeartMuLa checkpoints ready. Launch with: bash scripts/start_heartmula.sh")
PYEOF
