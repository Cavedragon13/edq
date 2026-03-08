#!/bin/bash
# Rebuild llama.cpp with Blackwell CUDA support (sm_120a)
# Run after every git pull on projects/llama.cpp
set -e

REPO="/srv/containers/edq/projects/llama.cpp"

echo "Rebuilding llama.cpp with CUDA (sm_120a)..."
cd "$REPO"

cmake -B build \
    -DGGML_CUDA=ON \
    -DCMAKE_CUDA_ARCHITECTURES="native" 2>&1 | grep -E "CUDA|arch|error|warning" || true

cmake --build build --config Release -j$(nproc)

echo ""
echo "Verifying..."
./build/bin/llama-cli --version 2>&1 | head -3
echo "Done."
