#!/bin/bash
# Pre-download Z-Anime AIO models (run once before first launch)
# Source: https://huggingface.co/SeeSee21/Z-Anime
# Downloads AIO FP8 variants (~6GB each) — model+VAE+text encoder in one file
# For BF16: set ZANIME_VARIANT=bf16 before running
set -e
cd /srv/containers/edq
source venv_zimage/bin/activate

VARIANT="${ZANIME_VARIANT:-fp8}"
MODEL_DIR="/srv/containers/edq/models/zanime"

echo "========================================="
echo " Z-Anime Model Downloader"
echo " Variant: $VARIANT (AIO — single file per model)"
echo " Destination: $MODEL_DIR"
echo "========================================="
echo ""

mkdir -p "$MODEL_DIR/aio"

python3 << PYEOF
import os, sys
from pathlib import Path
from huggingface_hub import hf_hub_download

MODEL_DIR = Path("/srv/containers/edq/models/zanime")
VARIANT = os.environ.get("ZANIME_VARIANT", "fp8")
REPO_ID = "SeeSee21/Z-Anime"

# AIO = All-In-One: model + VAE + text encoder in a single safetensors file
# Loads via ZImagePipeline.from_single_file() — simpler than separate components
AIO_FILES = [
    f"aio/z-anime-base-aio-{VARIANT}.safetensors",
    f"aio/z-anime-distill-8step-aio-{VARIANT}.safetensors",
    f"aio/z-anime-distill-4step-aio-{VARIANT}.safetensors",
]

for hf_path in AIO_FILES:
    dest = MODEL_DIR / hf_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        size_gb = dest.stat().st_size / 1e9
        print(f"  ✓ Already present: {hf_path} ({size_gb:.1f}GB)")
        continue
    print(f"  ⬇  Downloading: {hf_path}")
    try:
        hf_hub_download(
            repo_id=REPO_ID,
            filename=hf_path,
            local_dir=str(MODEL_DIR),
        )
        size_gb = (MODEL_DIR / hf_path).stat().st_size / 1e9
        print(f"  ✓  Saved ({size_gb:.1f}GB): {dest}")
    except Exception as e:
        print(f"  ❌  Failed: {hf_path} — {e}", file=sys.stderr)
        sys.exit(1)

print()
print("✅ All Z-Anime models downloaded.")
print(f"   Location: {MODEL_DIR}/aio/")
print()
print("Launch with: bash scripts/start_zanime.sh")
PYEOF
