#!/bin/bash
# Pre-download all ACE-Step 1.5 XL models (run once before first launch; ~28GB).
# Uses upstream's own downloader (acestep-download), which knows the repo ids,
# falls back HuggingFace <-> ModelScope, and skips models already present.
#   main bundle: acestep-v15-turbo DiT, VAE, 5Hz LM 1.7B, Qwen3-Embedding-0.6B
#   + acestep-v15-xl-turbo (the XL DiT this service runs, per .env ACESTEP_CONFIG_PATH)
set -e
cd /srv/containers/edq/projects/ACE-Step-1.5-xl
export ACESTEP_CHECKPOINTS_DIR=/srv/containers/edq/projects/ACE-Step-1.5-xl/checkpoints

.venv/bin/acestep-download --dir "$ACESTEP_CHECKPOINTS_DIR"
.venv/bin/acestep-download --dir "$ACESTEP_CHECKPOINTS_DIR" --model acestep-v15-xl-turbo --skip-main
echo "ACE-Step models ready in $ACESTEP_CHECKPOINTS_DIR. Launch with: bash scripts/start_ace_step.sh"
