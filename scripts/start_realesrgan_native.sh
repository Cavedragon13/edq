#!/bin/bash
# Real-ESRGAN — AI upscaling with multiple models
# Port: 8010
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="Real-ESRGAN"
PORT=8010
VENV="venv_realesrgan"
SCRIPT="scripts/realesrgan_server.py"
MODELS_DIR="/srv/containers/edq/models/realesrgan"

service_header "$SERVICE_NAME" "$PORT"
gpu_preflight "$PORT"
activate_venv "$VENV"
pip install -q fastapi uvicorn python-multipart 2>/dev/null || true
set_pytorch_env

for model_file in \
    RealESRGAN_x4plus.pth \
    RealESRGAN_x4plus_anime_6B.pth \
    RealESRGAN_x2plus.pth \
    realesr-general-x4v3.pth \
    GFPGANv1.3.pth
do
    if [ ! -s "$MODELS_DIR/$model_file" ]; then
        echo "❌ Missing Real-ESRGAN model: $MODELS_DIR/$model_file"
        echo "   Run: bash scripts/download_realesrgan_models.sh"
        exit 1
    fi
done

echo "🚀 Starting $SERVICE_NAME..."

if pgrep -f "realesrgan_server.py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup python "$SCRIPT" > /tmp/realesrgan.log 2>&1 &
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 30; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Service did not start in time — check /tmp/realesrgan.log"
        tail -10 /tmp/realesrgan.log
        exit 1
    fi
fi
