#!/bin/bash
# Download models for new tools (JustDubit, SoulX-Singer, DeepGen)
# Safe to run multiple times - uses Python API for reliable resumable downloads

set -e

MODELS_DIR="/srv/containers/edq/models"
mkdir -p "$MODELS_DIR"

echo "🚀 Starting background model downloads for new Dragonsuite tools..."
echo "This is safe to interrupt (Ctrl+C) and resume later."
echo ""

#############################################
# 1. SoulX-Singer Models (~8GB total)
#############################################
echo ""
echo "=== SoulX-Singer Models ==="
source /srv/containers/edq/venv_soulxsinger/bin/activate

python << 'PYEOF'
from huggingface_hub import snapshot_download
from pathlib import Path

models_dir = Path("/srv/containers/edq/models")

print("📦 Downloading Soul-AILab/SoulX-Singer...")
try:
    snapshot_download(
        repo_id="Soul-AILab/SoulX-Singer",
        local_dir=str(models_dir / "SoulX-Singer"),
        ignore_patterns=["*.git*", "README.md"]
    )
    print("✓ SoulX-Singer downloaded!")
except Exception as e:
    print(f"⚠️  Download failed: {e}")
    print("Run again to resume.")

print("\n📦 Downloading Soul-AILab/SoulX-Singer-Preprocess...")
try:
    snapshot_download(
        repo_id="Soul-AILab/SoulX-Singer-Preprocess",
        local_dir=str(models_dir / "SoulX-Singer-Preprocess"),
        ignore_patterns=["*.git*", "README.md"]
    )
    print("✓ SoulX-Singer-Preprocess downloaded!")
except Exception as e:
    print(f"⚠️  Download failed: {e}")
    print("Run again to resume.")
PYEOF

deactivate

#############################################
# 2. JustDubit Models (~50GB total)
#############################################
echo ""
echo "=== JustDubit Models (LARGE - ~50GB) ==="
echo "This will take a while..."

cd /srv/containers/edq/projects/just-dub-it

/home/edq/.local/bin/uv run python << 'PYEOF'
from huggingface_hub import snapshot_download
from pathlib import Path

models_dir = Path("/srv/containers/edq/models")

print("📦 Downloading justdubit/justdubit...")
print("⚠️  This is ~50GB - may take 1-2 hours on fast connection")
try:
    snapshot_download(
        repo_id="justdubit/justdubit",
        local_dir=str(models_dir / "justdubit"),
        ignore_patterns=["*.git*", "README.md"]
    )
    print("✓ JustDubit models downloaded!")
    print("\nLook for these files:")
    print("  - ltx-2-19b-dev.safetensors")
    print("  - ltx-2-19b-ic-lora-lipdubbing.safetensors")
    print("  - ltx-2-19b-distilled-lora-384.safetensors")
    print("  - ltx-2-spatial-upscaler-x2-1.0.safetensors")
    print("  - gemma-3-12b-it-qat-q4_0-unquantized/")
except Exception as e:
    print(f"⚠️  Download failed: {e}")
    print("Run again to resume - partial downloads are saved.")
PYEOF

cd /srv/containers/edq

#############################################
# 3. DeepGen Models (~10GB total)
#############################################
echo ""
echo "=== DeepGen 1.0 Models ==="
source /srv/containers/edq/venv_deepgen/bin/activate

python << 'PYEOF'
from huggingface_hub import snapshot_download
from pathlib import Path

models_dir = Path("/srv/containers/edq/models")

print("📦 Downloading deepgenteam/DeepGen-1.0...")
try:
    snapshot_download(
        repo_id="deepgenteam/DeepGen-1.0",
        local_dir=str(models_dir / "deepgen-1.0"),
        ignore_patterns=["*.git*", "README.md"]
    )
    print("✓ DeepGen models downloaded!")
except Exception as e:
    print(f"⚠️  Download failed: {e}")
    print("Run again to resume.")
PYEOF

deactivate

#############################################
# Summary
#############################################
echo ""
echo "======================================"
echo "✅ Model download script complete!"
echo "======================================"
echo ""
echo "Models saved to: $MODELS_DIR"
echo ""
echo "Check what was downloaded:"
echo "  ls -lh $MODELS_DIR/SoulX-Singer/"
echo "  ls -lh $MODELS_DIR/justdubit/"
echo "  ls -lh $MODELS_DIR/deepgen-1.0/"
echo ""
echo "Total disk space used: $(du -sh $MODELS_DIR 2>/dev/null | cut -f1)"
echo ""
echo "Next steps:"
echo "  1. Update model paths in scripts (see docs/model-downloads-guide.md)"
echo "  2. Test services:"
echo "     bash scripts/start_soulxsinger.sh"
echo "     bash scripts/start_justdubit.sh"
echo "     bash scripts/start_deepgen.sh"
