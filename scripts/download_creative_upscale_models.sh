#!/bin/bash
# Download models for Creative Upscaler (FLUX + ControlNet Tile)
# Safe to interrupt (Ctrl+C) and resume - downloads are resumable
#
# Models downloaded (~28GB total):
#   - jasperai/Flux.1-dev-Controlnet-Upscaler (~5GB)
#   - black-forest-labs/FLUX.1-dev diffusers components (~23GB)
#
# Usage: bash scripts/download_creative_upscale_models.sh

set -e

TOOL_NAME="Creative Upscaler"
VENV_PATH="/srv/containers/edq/venv_flux2"
MODELS_DIR="/srv/containers/edq/models/creative_upscale"
ESTIMATED_SIZE="28 GB"

mkdir -p "$MODELS_DIR"

echo "🚀 Downloading $TOOL_NAME models (~$ESTIMATED_SIZE)..."
echo "This is safe to interrupt (Ctrl+C) and resume later."
echo ""
echo "Models to download:"
echo "  1. jasperai/Flux.1-dev-Controlnet-Upscaler (~5GB)"
echo "  2. black-forest-labs/FLUX.1-dev (~23GB)"
echo ""

# Activate venv
source "$VENV_PATH/bin/activate"

# Download both models
python << 'PYEOF'
from huggingface_hub import snapshot_download
from pathlib import Path
import sys

models_dir = Path("/srv/containers/edq/models/creative_upscale")

# Download ControlNet (~5GB)
print("📦 Downloading FLUX.1-dev-Controlnet-Upscaler (~5GB)...")
print(f"    → {models_dir}/controlnet")
try:
    snapshot_download(
        repo_id="jasperai/Flux.1-dev-Controlnet-Upscaler",
        local_dir=str(models_dir / "controlnet"),
        ignore_patterns=["*.git*", "README.md", "*.md"]
    )
    print("✓ ControlNet downloaded!\n")
except Exception as e:
    print(f"⚠️  Download failed: {e}")
    print("Partial downloads are saved - run again to resume.")
    sys.exit(1)

# Download FLUX.1-dev diffusers components (~23GB)
print("📦 Downloading FLUX.1-dev (~23GB, this takes a while)...")
print(f"    → {models_dir}/flux_dev")
try:
    snapshot_download(
        repo_id="black-forest-labs/FLUX.1-dev",
        local_dir=str(models_dir / "flux_dev"),
        ignore_patterns=[
            "*.git*",
            "README.md",
            "*.md",
            # Not used by FluxControlNetPipeline.from_pretrained(local_dir).
            # Pulling this monolith adds ~23GB and can make first install look hung.
            "flux1-dev.safetensors",
        ]
    )
    print("✓ FLUX.1-dev downloaded!\n")
except Exception as e:
    print(f"⚠️  Download failed: {e}")
    print("Partial downloads are saved - run again to resume.")
    sys.exit(1)

print("Downloaded files:")
for item in sorted(models_dir.rglob("*.safetensors")):
    size = item.stat().st_size / (1024**3)
    print(f"  {item.relative_to(models_dir)} ({size:.2f} GB)")

PYEOF

deactivate

echo ""
echo "======================================"
echo "✅ Models ready for $TOOL_NAME!"
echo "======================================"
echo ""
echo "Models location: $MODELS_DIR"
echo ""
echo "Next: bash scripts/start_creative_upscale.sh"
echo ""
