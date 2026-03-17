#!/bin/bash
# Pre-download Hunyuan3D-2 models from Tencent
# Shape model: tencent/Hunyuan3D-2mini (~4GB)
# Texture model: tencent/Hunyuan3D-2 (~6GB)
# Per SOP: models must be present BEFORE first run

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/venv_hunyuan3d"

echo "🧊 Hunyuan3D-2 — Pre-downloading models"
echo "========================================="
echo "  tencent/Hunyuan3D-2mini — shape model (~4GB)"
echo "  tencent/Hunyuan3D-2     — texture model (~6GB)"
echo ""

if [ ! -d "$VENV_DIR" ]; then
    echo "❌ venv_hunyuan3d not found. Run setup first:"
    echo "   bash scripts/start_hunyuan3d.sh  (first run will install deps)"
    exit 1
fi

source "$VENV_DIR/bin/activate"

python3 << 'PYEOF'
import sys

print("Loading HuggingFace hub...")
try:
    from huggingface_hub import snapshot_download
except ImportError:
    print("❌ huggingface_hub not available in venv_hunyuan3d")
    sys.exit(1)

print("")
print("📥 Downloading tencent/Hunyuan3D-2mini (shape model)...")
snapshot_download(
    repo_id="tencent/Hunyuan3D-2mini",
    ignore_patterns=["*.git*", ".gitattributes"],
)
print("✅ Hunyuan3D-2mini downloaded")

print("")
print("📥 Downloading tencent/Hunyuan3D-2 (texture model, ~6GB)...")
snapshot_download(
    repo_id="tencent/Hunyuan3D-2",
    ignore_patterns=["*.git*", ".gitattributes"],
)
print("✅ Hunyuan3D-2 downloaded")

print("")
print("✅ All Hunyuan3D-2 models ready.")
print("   Models cached in ~/.cache/huggingface/hub/")
print("   Launch with: bash scripts/start_hunyuan3d.sh")
PYEOF
