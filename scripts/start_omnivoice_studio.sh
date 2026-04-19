#!/bin/bash
# OmniVoice-Studio - Cinematic Video Dubbing Studio (Docker)
# Transcribe → Translate → Re-voice → Mux with stem separation, timeline editor
# Port 8051 (remapped from Docker's :8000), LAN accessible
set -euo pipefail

cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="OmniVoice Studio"
PORT=8051
DOCKER_COMPOSE_FILE="$DRAGONSUITE_ROOT/docker/omnivoice-studio/docker-compose.yml"
OUTPUT_DIR="$HOME/ai_generated/omnivoice_studio"

service_header "$SERVICE_NAME" "$PORT"

echo "🔧 Pre-flight checks..."
vram_status
clear_port "$PORT"
echo "✓ VRAM status:"
vram_status
echo ""

if [ ! -f "$DOCKER_COMPOSE_FILE" ]; then
    echo "❌ Docker Compose file not found: $DOCKER_COMPOSE_FILE"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

echo "🚀 Starting $SERVICE_NAME via Docker Compose..."

# Ensure HF cache directory exists for model mounting
mkdir -p "$DRAGONSUITE_ROOT/cache_huggingface"

# Load .env for any HF_TOKEN if present
if [ -f "$DRAGONSUITE_ROOT/.env" ]; then
    set -a
    source "$DRAGONSUITE_ROOT/.env"
    set +a
fi

# Build the Docker image (one-time or on updates)
echo "🔨 Building Docker image from source..."
if ! docker compose -f "$DOCKER_COMPOSE_FILE" build --pull 2>&1 | tail -20; then
    echo "❌ Docker build failed"
    exit 1
fi

# Start the container
if docker compose -f "$DOCKER_COMPOSE_FILE" up -d; then
    echo "⏳ Waiting for service to become healthy..."
    if wait_for_port "$PORT" 300; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
        echo "   Output folder: $OUTPUT_DIR"
        echo ""
    else
        echo "❌ Service did not respond in time — checking logs..."
        docker compose -f "$DOCKER_COMPOSE_FILE" logs --tail=50
        exit 1
    fi
else
    echo "❌ Failed to start container — checking Docker logs..."
    docker compose -f "$DOCKER_COMPOSE_FILE" logs --tail=50
    exit 1
fi
