#!/bin/bash
# Download Florence-2 captioning model for AI Toolkit
# Florence-2 is used for auto-captioning training images in the UI

set -e

VENV="/srv/containers/edq/venv_ai_toolkit"

echo "📥 Downloading AI Toolkit models..."
echo ""

if [ ! -d "$VENV" ]; then
    echo "❌ venv_ai_toolkit not found. Start the service once to create it."
    exit 1
fi

source "$VENV/bin/activate"

python3 << 'PYEOF'
from huggingface_hub import snapshot_download

print("Downloading Florence-2 (image captioner for auto-captions)...")
snapshot_download(
    repo_id="multimodalart/Florence-2-large-no-flash-attn",
    ignore_patterns=["*.msgpack", "*.h5", "flax_model*"],
)
print("✓ Florence-2 done")
print("")
print("All models ready. AI captions will work on next launch.")
PYEOF
