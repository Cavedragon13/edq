#!/usr/bin/env bash
# Create Mira-Scene's isolated stage environments with Blackwell-safe cu128 wheels.
set -euo pipefail

ROOT=/srv/containers/edq
CONDA="$ROOT/opt/miniforge3/bin/conda"
ENV_ROOT="$ROOT/conda_envs"
TORCH_INDEX=https://download.pytorch.org/whl/cu128
mkdir -p "$ENV_ROOT"

ensure_env() {
  local name="$1" python_version="$2"
  local prefix="$ENV_ROOT/mira-$name"
  if [ ! -x "$prefix/bin/python" ]; then
    "$CONDA" create -y --prefix "$prefix" "python=$python_version" pip "setuptools<81"
  fi
  "$prefix/bin/python" -m pip install --upgrade \
    --index-url "$TORCH_INDEX" \
    torch==2.7.1+cu128 torchvision==0.22.1+cu128
  "$prefix/bin/python" -c 'import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())'
}

ensure_env segmentation 3.11
ensure_env geometry 3.11
ensure_env ccm 3.11
ensure_env sam3d 3.11
ensure_env trellis2 3.10
echo 'Mira-Scene base environments are ready.'
