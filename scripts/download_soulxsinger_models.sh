#!/bin/bash
# Download models for SoulX-Singer zero-shot singing voice synthesis
# Safe to interrupt (Ctrl+C) and resume - downloads are resumable
#
# Models downloaded:
#   - Soul-AILab/SoulX-Singer (~2.7GB) - main synthesis model
#   - Soul-AILab/SoulX-Singer-Preprocess (~400MB) - RMVPE for transcription/MIDI
#
# Usage: bash scripts/download_soulxsinger_models.sh

set -e

TOOL_NAME="SoulX-Singer"
VENV_PATH="/srv/containers/edq/venv_soulxsinger"
MODELS_DIR="/srv/containers/edq/models"
PROJECT_DIR="/srv/containers/edq/projects/SoulX-Singer"

echo "🎤 Downloading $TOOL_NAME models..."
echo "This is safe to interrupt (Ctrl+C) and resume later."
echo ""

source "$VENV_PATH/bin/activate"

python << PYEOF
from huggingface_hub import snapshot_download
from pathlib import Path

models_dir = Path("$MODELS_DIR")
models_dir.mkdir(exist_ok=True)

# Download main model (~2.7GB)
print("📦 Downloading SoulX-Singer main model (~2.7GB)...")
try:
    snapshot_download(
        repo_id="Soul-AILab/SoulX-Singer",
        local_dir=str(models_dir / "SoulX-Singer"),
        ignore_patterns=["*.git*", "README.md", "*.md"]
    )
    print("✓ Main model downloaded!\n")
except Exception as e:
    print(f"⚠️  Download failed: {e}")
    print("Partial downloads are saved - run again to resume.")
    import sys; sys.exit(1)

# Download preprocess model (~400MB) - needed for transcription/MIDI
print("📦 Downloading SoulX-Singer-Preprocess (~400MB)...")
try:
    snapshot_download(
        repo_id="Soul-AILab/SoulX-Singer-Preprocess",
        local_dir=str(models_dir / "SoulX-Singer-Preprocess"),
        ignore_patterns=["*.git*", "README.md", "*.md"]
    )
    print("✓ Preprocess model downloaded!\n")
except Exception as e:
    print(f"⚠️  Preprocess download failed: {e}")
    print("Partial downloads are saved - run again to resume.")
    import sys; sys.exit(1)

print("✓ All models downloaded!")
PYEOF

deactivate

# Create symlinks so webui.py can find models at pretrained_models/
echo ""
echo "🔗 Creating symlinks in project directory..."
mkdir -p "$PROJECT_DIR/pretrained_models"

if [ ! -L "$PROJECT_DIR/pretrained_models/SoulX-Singer" ]; then
    ln -sfn "$MODELS_DIR/SoulX-Singer" "$PROJECT_DIR/pretrained_models/SoulX-Singer"
    echo "✓ Linked pretrained_models/SoulX-Singer"
else
    echo "✓ Symlink already exists: pretrained_models/SoulX-Singer"
fi

if [ ! -L "$PROJECT_DIR/pretrained_models/SoulX-Singer-Preprocess" ]; then
    ln -sfn "$MODELS_DIR/SoulX-Singer-Preprocess" "$PROJECT_DIR/pretrained_models/SoulX-Singer-Preprocess"
    echo "✓ Linked pretrained_models/SoulX-Singer-Preprocess"
else
    echo "✓ Symlink already exists: pretrained_models/SoulX-Singer-Preprocess"
fi

echo ""
echo "======================================"
echo "✅ Models ready for $TOOL_NAME!"
echo "======================================"
echo ""
echo "Models location: $MODELS_DIR/SoulX-Singer"
echo "               : $MODELS_DIR/SoulX-Singer-Preprocess"
echo ""
echo "Next: bash scripts/start_soulxsinger.sh"
echo ""
