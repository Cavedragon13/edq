#!/bin/bash
# Download Real-ESRGAN/GFPGAN weights for offline first-run use.
set -e

MODELS_DIR="/srv/containers/edq/models/realesrgan"
mkdir -p "$MODELS_DIR"

download() {
    local url="$1"
    local out="$2"
    if [ -s "$out" ]; then
        echo "✓ $(basename "$out") already exists"
        return
    fi
    echo "📦 Downloading $(basename "$out")..."
    curl -L --fail --continue-at - --output "$out" "$url"
}

download "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth" \
    "$MODELS_DIR/RealESRGAN_x4plus.pth"
download "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth" \
    "$MODELS_DIR/RealESRGAN_x4plus_anime_6B.pth"
download "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth" \
    "$MODELS_DIR/RealESRGAN_x2plus.pth"
download "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth" \
    "$MODELS_DIR/realesr-general-x4v3.pth"
download "https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.3.pth" \
    "$MODELS_DIR/GFPGANv1.3.pth"

echo ""
echo "✅ Real-ESRGAN models ready at $MODELS_DIR"
