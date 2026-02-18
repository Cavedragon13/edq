#!/bin/bash
# TEMPLATE: Download models for a new tool
# Copy this template when adding a new AI tool that requires model downloads
#
# Usage:
#   1. Copy this file: cp scripts/template_download_models.sh scripts/download_TOOLNAME_models.sh
#   2. Replace ALL_CAPS placeholders with actual values
#   3. Make executable: chmod +x scripts/download_TOOLNAME_models.sh
#   4. Test: bash scripts/download_TOOLNAME_models.sh
#   5. Document in tool's setup guide

set -e

# REPLACE THESE
TOOL_NAME="TOOLNAME"                                              # e.g., "soulxsinger"
VENV_PATH="/srv/containers/edq/venv_TOOLNAME"                    # e.g., "/srv/containers/edq/venv_soulxsinger"
MODELS_DIR="/srv/containers/edq/models/TOOLNAME"                 # e.g., "/srv/containers/edq/models/soulxsinger"
HF_REPO="ORG/REPO"                                               # e.g., "Soul-AILab/SoulX-Singer"
ESTIMATED_SIZE="XX GB"                                           # e.g., "8 GB"

mkdir -p "$MODELS_DIR"

echo "🚀 Downloading $TOOL_NAME models (~$ESTIMATED_SIZE)..."
echo "This is safe to interrupt (Ctrl+C) and resume later."
echo ""

# Activate venv
source "$VENV_PATH/bin/activate"

# Download using Python API (most reliable)
python << PYEOF
from huggingface_hub import snapshot_download
from pathlib import Path

models_dir = Path("$MODELS_DIR")

print("📦 Downloading $HF_REPO...")
print(f"    → {models_dir}")

try:
    snapshot_download(
        repo_id="$HF_REPO",
        local_dir=str(models_dir),
        ignore_patterns=["*.git*", "README.md", "*.md"]  # Skip unnecessary files
    )
    print(f"✓ Downloaded successfully!")
    print(f"✓ Location: {models_dir}")

    # List what was downloaded
    print("\nDownloaded files:")
    for item in sorted(models_dir.rglob("*")):
        if item.is_file():
            size = item.stat().st_size / (1024**3)  # GB
            print(f"  {item.name} ({size:.2f} GB)")

except Exception as e:
    print(f"⚠️  Download failed: {e}")
    print("\nPartial downloads are saved - run again to resume.")
    exit(1)
PYEOF

deactivate

echo ""
echo "======================================"
echo "✅ Models ready for $TOOL_NAME!"
echo "======================================"
echo ""
echo "Models location: $MODELS_DIR"
echo ""
echo "Next steps:"
echo "  1. Update model paths in scripts if needed"
echo "  2. Launch tool: bash scripts/start_TOOLNAME.sh"
echo ""

# OPTIONAL: Add verification
# echo "Verifying models..."
# if [ -f "$MODELS_DIR/expected_file.safetensors" ]; then
#     echo "✓ Core model found"
# else
#     echo "⚠️  Warning: Expected model file not found"
# fi
