#!/bin/bash
# Download Voxtral-4B-TTS-2603 model weights to HF cache
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
VENV="$ROOT_DIR/venv_voxtral"

source "$VENV/bin/activate"

echo "📥 Downloading mistralai/Voxtral-4B-TTS-2603 (~16GB, bfloat16)..."
echo "   Destination: ~/.cache/huggingface/hub"
echo "   This download is resumable if interrupted."
echo ""

python3 << 'PYEOF'
from huggingface_hub import snapshot_download, hf_hub_download
import sys

model_id = "mistralai/Voxtral-4B-TTS-2603"

print(f"Starting download of {model_id}...")
path = snapshot_download(
    repo_id=model_id,
    ignore_patterns=["original/*"],  # voice_embedding/*.pt are required — do NOT exclude *.pt
)
print(f"\n✓ Model downloaded to: {path}")

# Verify voice embeddings are present (they're in voice_embedding/*.pt)
import os
ve_dir = os.path.join(path, "voice_embedding")
if os.path.isdir(ve_dir):
    pts = [f for f in os.listdir(ve_dir) if f.endswith(".pt")]
    print(f"✓ Voice embeddings: {len(pts)} files found")
else:
    print("⚠️  voice_embedding/ directory not found — voice loading will fail")
PYEOF
