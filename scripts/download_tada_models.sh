#!/bin/bash
# Pre-download TADA-3B-ML model and codec encoder
# Eliminates first-launch wait time (~6GB total)
# Per SOP: models must be present BEFORE first run

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/venv_tada"

echo "🎙️  TADA TTS — Pre-downloading models"
echo "========================================"
echo "  TADA-3B-ML (Llama 3.2 3B base, ~6GB)"
echo "  HumeAI/tada-codec encoder"
echo ""

if [ ! -d "$VENV_DIR" ]; then
    echo "❌ venv_tada not found. Run setup first:"
    echo "   python3 -m venv $VENV_DIR"
    exit 1
fi

source "$VENV_DIR/bin/activate"

python3 << 'PYEOF'
import sys

print("Loading HuggingFace hub...")
try:
    from huggingface_hub import snapshot_download
except ImportError:
    print("❌ huggingface_hub not available in venv_tada")
    sys.exit(1)

print("")
print("📥 Downloading HumeAI/tada-codec (encoder)...")
snapshot_download(
    repo_id="HumeAI/tada-codec",
    ignore_patterns=["*.git*", ".gitattributes"],
)
print("✅ tada-codec downloaded")

print("")
print("📥 Downloading HumeAI/tada-3b-ml (~6GB, be patient)...")
snapshot_download(
    repo_id="HumeAI/tada-3b-ml",
    ignore_patterns=["*.git*", ".gitattributes"],
)
print("✅ tada-3b-ml downloaded")

print("")
print("✅ All TADA models ready.")
print("   Models cached in ~/.cache/huggingface/hub/")
print("   Launch with: bash scripts/start_tada.sh")
PYEOF
