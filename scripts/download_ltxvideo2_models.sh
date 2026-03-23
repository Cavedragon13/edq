#!/bin/bash
# download_ltxvideo2_models.sh — Download LTX-2 (19B) for port 8016
# Run ONCE before first launch. Idempotent — safe to re-run.
# LTX-2.3 skipped: no diffusers support yet. Using LTX-2 (19B) which has full support.
set -e

VENV="/srv/containers/edq/venv_ltxvideo"
MODEL_DIR="/srv/containers/edq/models/ltxvideo_2"

if [ ! -f "$VENV/bin/activate" ]; then
    echo "❌ venv_ltxvideo not found. Create it first:"
    echo "   python3 -m venv $VENV"
    echo "   source $VENV/bin/activate"
    echo "   pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128"
    echo "   pip install diffusers transformers accelerate huggingface_hub imageio imageio-ffmpeg gradio"
    exit 1
fi

source "$VENV/bin/activate"

# Ensure diffusers is current (LTX2Pipeline added in recent diffusers releases)
echo "📦 Upgrading diffusers and dependencies..."
pip install -q --upgrade diffusers transformers accelerate

MODEL_DIR_PY="$MODEL_DIR" python3 << 'PYEOF'
import os
from huggingface_hub import snapshot_download

model_dir = os.environ["MODEL_DIR_PY"]
os.makedirs(model_dir, exist_ok=True)

# VERIFIED: Lightricks/LTX-2 exists on HuggingFace with full diffusers support (LTX2Pipeline).
# LTX-2.3 (22B) skipped — no diffusers support yet (model card says "coming soon").
repo_id = "Lightricks/LTX-2"

print(f"Downloading {repo_id} (~38GB at bf16, this will take a while)...")
snapshot_download(
    repo_id=repo_id,
    local_dir=model_dir,
    ignore_patterns=["*.md", "*.txt", ".gitattributes"],
)
print(f"  ✅ → {model_dir}")
print("\n✅ LTX-2 (19B) downloaded.")
PYEOF
