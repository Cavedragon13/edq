#!/bin/bash
# Download DeepGen 1.0 diffusers models.
# Safe to interrupt and resume. Required before first Dashboard launch.
set -e

cd /srv/containers/edq

VENV_PATH="/srv/containers/edq/venv_deepgen"
MODELS_DIR="/srv/containers/edq/models/deepgen-1.0-diffusers"

if [ ! -d "$VENV_PATH" ]; then
    echo "❌ venv_deepgen not found at $VENV_PATH"
    echo "   Run: bash scripts/setup_deepgen_diffusers.sh"
    exit 1
fi

source "$VENV_PATH/bin/activate"
mkdir -p "$MODELS_DIR"

python << 'PYEOF'
from pathlib import Path
from huggingface_hub import snapshot_download

models_dir = Path("/srv/containers/edq/models/deepgen-1.0-diffusers")
print("Downloading deepgenteam/DeepGen-1.0-diffusers (~14GB)...")
snapshot_download(
    repo_id="deepgenteam/DeepGen-1.0-diffusers",
    local_dir=str(models_dir),
    ignore_patterns=["*.git*", "README.md", "*.md"],
)

required = [
    models_dir / "model_index.json",
    models_dir / "deepgen_pipeline.py",
    models_dir / "connector" / "model.safetensors",
    models_dir / "transformer" / "diffusion_pytorch_model.safetensors",
    models_dir / "vae" / "diffusion_pytorch_model.safetensors",
    models_dir / "vlm" / "model.safetensors.index.json",
]
missing = [str(path) for path in required if not path.exists() or path.stat().st_size == 0]
incomplete = list(models_dir.glob("**/.cache/huggingface/download/*.incomplete"))
if missing or incomplete:
    if missing:
        print("Missing files:")
        for path in missing:
            print(f"  {path}")
    if incomplete:
        print("Incomplete shards remain:")
        for path in incomplete:
            print(f"  {path}")
    raise SystemExit(1)

print("Downloaded safetensors:")
for path in sorted(models_dir.rglob("*.safetensors")):
    print(f"  {path.relative_to(models_dir)} ({path.stat().st_size / (1024 ** 3):.2f} GB)")
PYEOF

echo ""
echo "✅ DeepGen models ready at $MODELS_DIR"
echo "Next: bash scripts/start_deepgen.sh"
