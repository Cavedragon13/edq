#!/bin/bash
# download_wan_1b_models.sh — Download Wan2.1-T2V-1.3B (diffusers format)
# Run ONCE before first launch. Idempotent — safe to re-run.
set -e

VENV="/srv/containers/edq/venv_wan_1b"
MODEL_DIR="/srv/containers/edq/models/wan_1b"

if [ ! -f "$VENV/bin/activate" ]; then
    echo "❌ venv_wan_1b not found. Run: python3 -m venv $VENV first."
    exit 1
fi

source "$VENV/bin/activate"
echo "🔽 Downloading Wan2.1-T2V-1.3B (~3.5GB)..."

python3 << 'PYEOF'
import os
from huggingface_hub import snapshot_download

model_dir = "/srv/containers/edq/models/wan_1b"
os.makedirs(model_dir, exist_ok=True)

print("Downloading Wan-AI/Wan2.1-T2V-1.3B-Diffusers...")
snapshot_download(
    repo_id="Wan-AI/Wan2.1-T2V-1.3B-Diffusers",
    local_dir=model_dir,
    ignore_patterns=["*.md", "*.txt", ".gitattributes"],
)
print(f"✅ Done → {model_dir}")
PYEOF
