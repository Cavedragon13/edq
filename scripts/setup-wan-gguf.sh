#!/bin/bash

# Wan2.2-Animate-14B GGUF Setup Script (Optimized for 16GB VRAM)
# Uses quantized models that will run on RTX 5070 Ti

set -e

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  Wan2.2-Animate-14B GGUF Setup (16GB VRAM Compatible)         ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "This will install:"
echo "  • ComfyUI (AI workflow interface)"
echo "  • GGUF quantized models (fits in 16GB VRAM!)"
echo "  • Required custom nodes and dependencies"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
fi

# Install system dependencies
echo ""
echo "Step 1: Installing system dependencies..."
sudo apt update
sudo apt install -y python3-pip python3-venv git git-lfs wget

# Create project directory
echo ""
echo "Step 2: Setting up directories..."
cd ~
mkdir -p comfyui-wan
cd comfyui-wan

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip setuptools wheel

# Clone ComfyUI
echo ""
echo "Step 3: Cloning ComfyUI..."
if [ ! -d "ComfyUI" ]; then
    git clone https://github.com/comfyanonymous/ComfyUI.git
    cd ComfyUI
else
    cd ComfyUI
    git pull
fi

# Install PyTorch with CUDA
echo ""
echo "Step 4: Installing PyTorch with CUDA..."
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128

# Install ComfyUI requirements
echo ""
echo "Step 5: Installing ComfyUI dependencies..."
pip install -r requirements.txt

# Install ComfyUI-GGUF custom node
echo ""
echo "Step 6: Installing ComfyUI-GGUF custom node..."
cd custom_nodes
if [ ! -d "ComfyUI-GGUF" ]; then
    git clone https://github.com/city96/ComfyUI-GGUF.git
    cd ComfyUI-GGUF
else
    cd ComfyUI-GGUF
    git pull
fi
pip install -r requirements.txt
cd ../..

# Create model directories
echo ""
echo "Step 7: Creating model directories..."
mkdir -p models/unet
mkdir -p models/text_encoders
mkdir -p models/vae

# Download quantized model
echo ""
echo "Step 8: Downloading GGUF quantized model..."
echo "Available quantization levels:"
echo "  1. Q2_K (6.46 GB)  - Fastest, lower quality"
echo "  2. Q3_K_S (7.97 GB) - Good balance"
echo "  3. Q4_K_S (10.6 GB) - Recommended (best balance)"
echo "  4. Q5_K_S (12.3 GB) - Better quality"
echo "  5. Q6_K (14.6 GB)  - High quality (tight fit)"
echo ""
read -p "Select quantization [1-5] (default: 3): " quant_choice
quant_choice=${quant_choice:-3}

case $quant_choice in
    1) QUANT="Q2_K" ;;
    2) QUANT="Q3_K_S" ;;
    3) QUANT="Q4_K_S" ;;
    4) QUANT="Q5_K_S" ;;
    5) QUANT="Q6_K" ;;
    *) QUANT="Q4_K_S" ;;
esac

echo "Downloading ${QUANT} quantization..."
pip install "huggingface_hub[cli]"

# Download main model (GGUF)
huggingface-cli download QuantStack/Wan2.2-Animate-14B-GGUF \
    Wan2.2-Animate-14B-${QUANT}.gguf \
    --local-dir models/unet \
    --local-dir-use-symlinks False

# Download text encoder (choose safetensors for better compatibility)
echo ""
echo "Step 9: Downloading text encoder..."
huggingface-cli download Comfy-Org/Wan_2.2_ComfyUI_Repackaged \
    split_files/text_encoders/umt5-xxl-encoder.safetensors \
    --local-dir . \
    --local-dir-use-symlinks False
mv split_files/text_encoders/umt5-xxl-encoder.safetensors models/text_encoders/

# Download VAE
echo ""
echo "Step 10: Downloading VAE..."
huggingface-cli download Comfy-Org/Wan_2.2_ComfyUI_Repackaged \
    split_files/vae/Wan2.1_VAE.safetensors \
    --local-dir . \
    --local-dir-use-symlinks False
mv split_files/vae/Wan2.1_VAE.safetensors models/vae/

# Cleanup
rm -rf split_files

# Download example workflow
echo ""
echo "Step 11: Downloading example workflow..."
wget -O workflows/wan_animate_example.json \
    "https://huggingface.co/QuantStack/Wan2.2-Animate-14B-GGUF/resolve/main/example_workflow/wan%20animate%20native.json" \
    2>/dev/null || echo "Workflow download failed (optional)"

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                    Installation Complete!                      ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "✅ Quantization level: ${QUANT}"
echo "✅ ComfyUI installed with GGUF support"
echo "✅ Models downloaded and configured"
echo ""
echo "🚀 To start ComfyUI:"
echo "   cd ~/comfyui-wan/ComfyUI"
echo "   source ../venv/bin/activate"
echo "   python main.py"
echo ""
echo "Then open: http://localhost:8188"
echo ""
echo "📖 Example workflow saved to: workflows/wan_animate_example.json"
echo ""
