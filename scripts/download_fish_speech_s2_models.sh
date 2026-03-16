#!/bin/bash
# Download Fish Audio S2-Pro model weights
# Model: fishaudio/s2-pro (4B dual-AR, ~8GB)
# Replaces: openaudio-s1-mini (0.5B)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
FISH_SPEECH_DIR="$PROJECT_DIR/projects/fish-speech"
VENV_DIR="$PROJECT_DIR/venv_fish_speech"
MODEL_DIR="$FISH_SPEECH_DIR/checkpoints/s2-pro"

echo "🐟 Fish Audio S2-Pro Model Download"
echo "===================================="
echo "Model: fishaudio/s2-pro (~8GB)"
echo "Destination: $MODEL_DIR"
echo ""

if [ ! -d "$VENV_DIR" ]; then
    echo "❌ venv_fish_speech not found. Run start_fish_speech.sh first to create it."
    exit 1
fi

source "$VENV_DIR/bin/activate"

mkdir -p "$MODEL_DIR"

python3 << 'PYEOF'
import os
import sys
from pathlib import Path
from huggingface_hub import snapshot_download

model_dir = Path(os.environ.get("MODEL_DIR", "")).expanduser()
if not model_dir.is_absolute():
    print("❌ MODEL_DIR not set")
    sys.exit(1)

print("📥 Downloading fishaudio/s2-pro...")
print("   This model is ~8GB — please be patient")
print("")

snapshot_download(
    repo_id="fishaudio/s2-pro",
    local_dir=str(model_dir),
    ignore_patterns=["*.git*", ".gitattributes"],
)

print(f"✅ Download complete → {model_dir}")
codec = model_dir / "codec.pth"
if codec.exists():
    print(f"✅ codec.pth present ({codec.stat().st_size / 1e9:.1f} GB)")
else:
    print("⚠️  codec.pth not found — model may be incomplete")
PYEOF

