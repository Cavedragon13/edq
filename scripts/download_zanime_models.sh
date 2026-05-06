#!/bin/bash
# Pre-download Z-Anime models — diffusers layout (run once before first launch)
# Source: https://huggingface.co/SeeSee21/Z-Anime
# Downloads the full diffusers/ subfolder (~30GB BF16) to:
#   /srv/containers/edq/models/zanime/diffusers/
# Note: AIO files in models/zanime/aio/ are ComfyUI format — not used by this service.
set -e
cd /srv/containers/edq
source venv_zimage/bin/activate

DEST="/srv/containers/edq/models/zanime"

echo "========================================="
echo " Z-Anime Model Downloader"
echo " Layout: diffusers (ZImagePipeline.from_pretrained)"
echo " Destination: $DEST/diffusers/"
echo " Size: ~30GB total"
echo "========================================="
echo ""

python3 << 'PYEOF'
from huggingface_hub import snapshot_download
from pathlib import Path

DEST = Path("/srv/containers/edq/models/zanime")

print("Downloading diffusers layout (transformer shards, VAE, text encoder, tokenizer, scheduler)...")
snapshot_download(
    "SeeSee21/Z-Anime",
    allow_patterns=["diffusers/*"],
    local_dir=str(DEST),
)

# Verify the key files are present
required = [
    DEST / "diffusers" / "model_index.json",
    DEST / "diffusers" / "transformer" / "diffusion_pytorch_model-00001-of-00002.safetensors",
    DEST / "diffusers" / "transformer" / "diffusion_pytorch_model-00002-of-00002.safetensors",
    DEST / "diffusers" / "vae" / "diffusion_pytorch_model.safetensors",
    DEST / "diffusers" / "text_encoder" / "model.safetensors",
]
for p in required:
    if p.exists():
        print(f"  ✓ {p.name} ({p.stat().st_size / 1e9:.1f}GB)")
    else:
        print(f"  ❌ MISSING: {p}")
        raise SystemExit(1)

print()
print("✅ Z-Anime models ready.")
print("   Launch with: bash scripts/start_zanime.sh")
PYEOF
