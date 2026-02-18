#!/bin/bash
set -e

echo "🖼️ DeepGen 1.0 - Model Zoo Setup"
echo "Downloads the two base architecture models required by DeepGen."
echo "These provide config + tokenizer + weights (~25GB total)."
echo "After download, weights are overridden by the local model.pt checkpoint."
echo ""
echo "Models:"
echo "  Qwen/Qwen2.5-VL-3B-Instruct     (~7GB)  - VLM backbone"
echo "  Skywork/UniPic2-SD3.5M-Kontext-2B (~18GB) - Diffusion backbone"
echo ""

VENV_PATH="/srv/containers/edq/venv_deepgen"
MODELS_DIR="/srv/containers/edq/models/deepgen-model-zoo"
PROJECT_DIR="/srv/containers/edq/projects/deepgen"

if [ ! -d "$VENV_PATH" ]; then
    echo "❌ venv_deepgen not found at $VENV_PATH"
    exit 1
fi

source "$VENV_PATH/bin/activate"
mkdir -p "$MODELS_DIR"

python << 'PYEOF'
from huggingface_hub import snapshot_download
from pathlib import Path

models_dir = Path("/srv/containers/edq/models/deepgen-model-zoo")

print("📦 Downloading Qwen/Qwen2.5-VL-3B-Instruct (~7GB)...")
try:
    snapshot_download(
        repo_id="Qwen/Qwen2.5-VL-3B-Instruct",
        local_dir=str(models_dir / "Qwen2.5-VL-3B-Instruct"),
        ignore_patterns=["*.git*"]
    )
    print("✓ Qwen2.5-VL-3B-Instruct downloaded!")
except Exception as e:
    print(f"⚠️  Failed: {e}")

print("")
print("📦 Downloading Skywork/UniPic2-SD3.5M-Kontext-2B (~18GB)...")
try:
    snapshot_download(
        repo_id="Skywork/UniPic2-SD3.5M-Kontext-2B",
        local_dir=str(models_dir / "UniPic2-SD3.5M-Kontext-2B"),
        ignore_patterns=["*.git*"]
    )
    print("✓ UniPic2-SD3.5M-Kontext-2B downloaded!")
except Exception as e:
    print(f"⚠️  Failed: {e}")

print("")
print("All downloads complete!")
PYEOF

# Create symlink in project directory so config's relative paths resolve
SYMLINK="$PROJECT_DIR/model_zoo"
if [ -L "$SYMLINK" ]; then
    echo "✓ model_zoo symlink already exists"
elif [ -d "$SYMLINK" ]; then
    echo "⚠️  model_zoo exists as a real directory at $SYMLINK"
    echo "    If it's empty, remove it and re-run to create symlink."
else
    ln -s "$MODELS_DIR" "$SYMLINK"
    echo "✓ Created symlink: $SYMLINK -> $MODELS_DIR"
fi

echo ""
echo "✓ DeepGen model zoo ready!"
echo "  Models at: $MODELS_DIR"
echo "  Symlink:   $SYMLINK"
echo ""
echo "Next step: bash scripts/start_deepgen.sh"
