#!/bin/bash
# Pre-download Z-Image Base / Turbo models and the ControlNet union checkpoint.
# Mirrors the exact repos start_zimage.sh checks with local_files_only before launch.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/venv_zimage"

echo "🖼️  Z-Image Base — Pre-downloading models"
echo "=========================================="

if [ ! -d "$VENV_DIR" ]; then
    echo "❌ venv_zimage not found. Run setup first:"
    echo "   python3 -m venv $VENV_DIR"
    exit 1
fi

source "$VENV_DIR/bin/activate"

python3 << 'PYEOF'
from huggingface_hub import hf_hub_download, snapshot_download

print("📥 Tongyi-MAI/Z-Image...")
snapshot_download("Tongyi-MAI/Z-Image", ignore_patterns=["*.git*", ".gitattributes"])
print("✅ Z-Image downloaded")

print("📥 Tongyi-MAI/Z-Image-Turbo...")
snapshot_download("Tongyi-MAI/Z-Image-Turbo", ignore_patterns=["*.git*", ".gitattributes"])
print("✅ Z-Image-Turbo downloaded")

print("📥 alibaba-pai/Z-Image-Turbo-Fun-Controlnet-Union-2.1...")
hf_hub_download(
    repo_id="alibaba-pai/Z-Image-Turbo-Fun-Controlnet-Union-2.1",
    filename="Z-Image-Turbo-Fun-Controlnet-Union-2.1.safetensors",
)
print("✅ ControlNet checkpoint downloaded")

print("")
print("✅ All Z-Image models ready.")
print("   Launch with: bash scripts/start_zimage.sh")
PYEOF
