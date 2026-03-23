#!/bin/bash
# download_ltxvideo_models.sh — Download LTX-Video-0.9.8-distilled + spatial upscaler
# Run ONCE before first launch. Idempotent — safe to re-run.
# Previous 0.9.7 models remain in models/ltxvideo and models/ltxvideo_upscaler
set -e

VENV="/srv/containers/edq/venv_ltxvideo"
MODEL_DIR="/srv/containers/edq/models/ltxvideo_098"
UPSCALER_DIR="/srv/containers/edq/models/ltxvideo_upscaler_098"

if [ ! -f "$VENV/bin/activate" ]; then
    echo "❌ venv_ltxvideo not found. Run: python3 -m venv $VENV first."
    exit 1
fi

source "$VENV/bin/activate"

# Ensure diffusers is current enough for 0.9.8 pipeline classes
# tiktoken required for 0.9.8 tokenizer (new in 0.9.8 vs 0.9.7)
pip install -q --upgrade diffusers transformers tiktoken sentencepiece protobuf

MODEL_DIR_PY="$MODEL_DIR" UPSCALER_DIR_PY="$UPSCALER_DIR" python3 << 'PYEOF'
import os
from huggingface_hub import snapshot_download

model_dir    = os.environ["MODEL_DIR_PY"]
upscaler_dir = os.environ["UPSCALER_DIR_PY"]

# RTFM_VERIFY: Confirm these exact repo IDs on https://huggingface.co/Lightricks
# before running. 0.9.7 used "LTX-Video-0.9.7-distilled" and "ltxv-spatial-upscaler-0.9.7"
# 0.9.8 likely follows the same pattern but verify the distilled variant exists.
MODELS = [
    # VERIFIED: correct repo ID for 0.9.8 distilled (not "LTX-Video-0.9.8-distilled")
    ("Lightricks/LTX-Video-0.9.8-13B-distilled", model_dir),
    # VERIFIED: no 0.9.8 upscaler exists — 0.9.7 upscaler is the latest
    ("Lightricks/ltxv-spatial-upscaler-0.9.7", upscaler_dir),
]

for repo_id, local_dir in MODELS:
    os.makedirs(local_dir, exist_ok=True)
    print(f"Downloading {repo_id}...")
    snapshot_download(
        repo_id=repo_id,
        local_dir=local_dir,
        ignore_patterns=["*.md", "*.txt", ".gitattributes"],
    )
    print(f"  ✅ → {local_dir}")

print("\n✅ All models downloaded.")
PYEOF
