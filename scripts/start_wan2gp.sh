#!/bin/bash
# Wan2GP Video Generator
# Port: 8002
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="Wan2GP Video Generator"
PORT=8002
VENV="venv_wan2gp"
WAN2GP_DIR="$DRAGONSUITE_ROOT/projects/Wan2GP"
OUTPUT_DIR="$HOME/ai_generated/wan2gp"

service_header "$SERVICE_NAME" "$PORT"
gpu_preflight "$PORT"
activate_venv "$VENV"
set_pytorch_env

mkdir -p "$OUTPUT_DIR"
export WAN2GP_OUTPUT_DIR="$OUTPUT_DIR"

echo "Recommended models for 16GB VRAM:"
echo "  - Wan 2.2 Ovi (6GB) - fastest"
echo "  - LTX 2 (8GB)"
echo "  - Flux 2 int8 (8GB)"
echo ""
echo "Output saves to: $OUTPUT_DIR"
echo ""
echo "🚀 Starting $SERVICE_NAME..."
echo "Press Ctrl+C to stop"
echo ""

cd "$WAN2GP_DIR"
python wgp.py --server-name 0.0.0.0 --server-port "$PORT"
