#!/bin/bash
# Create isolated DeepGen diffusers venv and install runtime dependencies.
set -e

VENV_PATH="/srv/containers/edq/venv_deepgen"

if [ ! -d "$VENV_PATH" ]; then
    python3 -m venv "$VENV_PATH"
fi

source "$VENV_PATH/bin/activate"
python -m pip install --upgrade pip setuptools wheel
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
python -m pip install \
    "diffusers==0.38.0" \
    "transformers==4.57.6" \
    "huggingface_hub==0.36.0" \
    "safetensors==0.8.0rc0" \
    accelerate einops gradio sentencepiece pillow qwen-vl-utils

python - <<'PYEOF'
import importlib.metadata as metadata

for package in [
    "torch",
    "torchvision",
    "diffusers",
    "transformers",
    "accelerate",
    "safetensors",
    "einops",
    "gradio",
    "huggingface_hub",
]:
    print(f"{package}: {metadata.version(package)}")
PYEOF

echo ""
echo "✅ DeepGen venv ready at $VENV_PATH"
echo "Next: bash /srv/containers/edq/scripts/download_deepgen_models.sh"
