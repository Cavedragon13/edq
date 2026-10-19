#!/bin/bash
# Build venv_uniforge3d for UniForge3D on Blackwell (sm_120).
# Upstream setup.sh pins torch 2.6+cu124 and flash-attn 2.7.3, which cannot run on
# an RTX 5070 Ti, so: torch 2.10.0+cu128 and a prebuilt flash-attn 2.8.3 wheel
# (mjun0812/flash-attention-prebuild-wheels) matching torch2.10/cu128/cp310.
# The CUDA extensions are compiled from upstream's pinned commits with CUDA 12.8 + gcc-13
# (nvcc 12.8 rejects the system default gcc-15).
set -e
cd /srv/containers/edq
export UV_HTTP_TIMEOUT=600
PY="/srv/containers/edq/venv_uniforge3d/bin/python"
APP="/srv/containers/edq/projects/UniForge3D"
DEPS="$APP/.deps"

[ -x "$PY" ] || uv venv --python 3.10 venv_uniforge3d

uv pip install --python "$PY" torch==2.10.0 torchvision==0.25.0 --index-url https://download.pytorch.org/whl/cu128
uv pip install --python "$PY" 'https://github.com/mjun0812/flash-attention-prebuild-wheels/releases/download/v0.9.0/flash_attn-2.8.3%2Bcu128torch2.10-cp310-cp310-linux_x86_64.whl'
uv pip install --python "$PY" setuptools==80.9.0 wheel ninja cmake==3.31.6 packaging \
    transformers==4.57.3 peft==0.17.1 "huggingface-hub>=0.36,<1" \
    "timm>=1.0,<2" "kornia>=0.8,<0.9" "numpy>=2.1,<2.3" \
    "Pillow>=10.4,<12" "safetensors>=0.7,<1" trimesh==4.6.3 \
    "opencv-python-headless>=4.10,<5" "easydict>=1.13,<2" \
    "tqdm>=4.66,<5" "scipy>=1.13,<2"
# Studio server (scripts/uniforge3d_server.py)
uv pip install --python "$PY" fastapi "uvicorn[standard]" python-multipart

mkdir -p "$DEPS"
[ -d "$DEPS/TRELLIS.2" ] || git clone --recursive https://github.com/microsoft/TRELLIS.2.git "$DEPS/TRELLIS.2"
git -C "$DEPS/TRELLIS.2" checkout 75fbf0183001ed9876c8dbb35de6b68552ee08bd
git -C "$DEPS/TRELLIS.2" submodule update --init --recursive
[ -d "$DEPS/CuMesh" ] || git clone --recursive https://github.com/JeffreyXiang/CuMesh.git "$DEPS/CuMesh"
git -C "$DEPS/CuMesh" checkout 12289e1062f0603f2f0d0771b02e1395d247f26f
git -C "$DEPS/CuMesh" submodule update --init --recursive
[ -d "$DEPS/FlexGEMM" ] || git clone --recursive https://github.com/JeffreyXiang/FlexGEMM.git "$DEPS/FlexGEMM"
git -C "$DEPS/FlexGEMM" checkout 6dd94a859c26ee8246888502eada3dd8ad85532e
git -C "$DEPS/FlexGEMM" submodule update --init --recursive
[ -d "$DEPS/nvdiffrast" ] || git clone --branch v0.4.0 https://github.com/NVlabs/nvdiffrast.git "$DEPS/nvdiffrast"

bash scripts/make_patched_cuda128.sh   # glibc>=2.41 vs CUDA 12.8 noexcept clash
export CUDA_HOME=/srv/containers/edq/opt/cuda-12.8-patched
export PATH="$CUDA_HOME/bin:$PATH"
export CC=gcc-13 CXX=g++-13 CUDAHOSTCXX=g++-13
export TORCH_CUDA_ARCH_LIST="12.0"
export MAX_JOBS=6

# Build isolation off: the extensions import torch at build time.
uv pip install --python "$PY" --no-build-isolation "$DEPS/nvdiffrast"
uv pip install --python "$PY" --no-build-isolation "$DEPS/CuMesh"
uv pip install --python "$PY" --no-build-isolation "$DEPS/FlexGEMM"
uv pip install --python "$PY" --no-build-isolation "$DEPS/TRELLIS.2/o-voxel"
echo "venv_uniforge3d ready"
