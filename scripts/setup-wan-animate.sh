#!/bin/bash

# Wan2.2-Animate-14B Setup Script
# This script installs and sets up the Wan2.2 animation model with Gradio interface

set -e

echo "=== Wan2.2-Animate-14B Installation ==="
echo ""
echo "⚠️  IMPORTANT: This model requires significant VRAM (45-75GB for single GPU)"
echo "Your RTX 5070 Ti (16GB) will need heavy optimizations or multi-GPU setup"
echo ""
read -p "Continue with installation? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    exit 1
fi

# Step 1: Install system dependencies
echo "Step 1: Installing system dependencies..."
sudo apt update
sudo apt install -y python3-pip python3-venv python3-dev git git-lfs wget

# Step 2: Install CUDA toolkit (if not already installed)
echo "Step 2: Checking CUDA installation..."
if ! command -v nvcc &> /dev/null; then
    echo "CUDA toolkit not found. Installing..."
    wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-keyring_1.1-1_all.deb
    sudo dpkg -i cuda-keyring_1.1-1_all.deb
    sudo apt update
    sudo apt install -y cuda-toolkit-12-6
    echo 'export PATH=/usr/local/cuda/bin:$PATH' >> ~/.bashrc
    echo 'export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH' >> ~/.bashrc
else
    echo "CUDA toolkit already installed"
fi

# Step 3: Create project directory and virtual environment
echo "Step 3: Setting up Python environment..."
cd ~
mkdir -p wan-animate
cd wan-animate

python3 -m venv venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip setuptools wheel

# Step 4: Clone repository
echo "Step 4: Cloning Wan2.2 repository..."
if [ ! -d "Wan2.2" ]; then
    git clone https://github.com/Wan-Video/Wan2.2.git
    cd Wan2.2
else
    cd Wan2.2
    git pull
fi

# Step 5: Install PyTorch with CUDA support
echo "Step 5: Installing PyTorch with CUDA 12.6..."
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128

# Step 6: Install dependencies
echo "Step 6: Installing model dependencies..."
pip install -r requirements.txt

# Step 7: Install additional packages for optimization
echo "Step 7: Installing optimization libraries..."
pip install gradio huggingface_hub accelerate bitsandbytes safetensors

# Step 8: Download model weights
echo "Step 8: Downloading model weights (this may take a while)..."
cd ..
mkdir -p models
pip install "huggingface_hub[cli]"
huggingface-cli download Wan-AI/Wan2.2-Animate-14B --local-dir ./models/Wan2.2-Animate-14B

echo ""
echo "=== Installation Complete! ==="
echo ""
echo "To run the Gradio interface:"
echo "  cd ~/wan-animate"
echo "  source venv/bin/activate"
echo "  python gradio_app.py"
echo ""
