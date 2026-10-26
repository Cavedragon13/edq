#!/bin/bash
# Build venv_qwen_image_21 for Qwen-Image 2.1 Studio (Dragonsuite port 8076).
# uv-managed Python 3.12 (docs/venvs.md interpreter policy), torch cu128 (Blackwell sm_120),
# pinned deps from scripts/requirements_qwen_image_21.txt. Safe to re-run.
set -e
cd /srv/containers/edq
export PATH="$HOME/.local/bin:$PATH"
VENV=/srv/containers/edq/venv_qwen_image_21
if [ ! -x "$VENV/bin/python" ]; then
    uv venv --seed --python 3.12 "$VENV"
fi
export VIRTUAL_ENV="$VENV"
"$VENV/bin/python" -m pip install --upgrade pip wheel
"$VENV/bin/python" -m pip install torch==2.11.0 torchvision==0.26.0 --index-url https://download.pytorch.org/whl/cu128
"$VENV/bin/python" -m pip install -r /srv/containers/edq/scripts/requirements_qwen_image_21.txt
"$VENV/bin/python" -c "import torch, diffusers, transformers, bitsandbytes; from diffusers import QwenImage21Pipeline; print('OK', torch.__version__, diffusers.__version__, transformers.__version__, bitsandbytes.__version__, torch.cuda.is_available())"
echo "venv ready: $VENV"
