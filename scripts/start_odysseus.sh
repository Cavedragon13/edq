#!/bin/bash
# Odysseus - self-hosted AI workspace
# Port: 8057
set -e

cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="Odysseus"
PORT=8057
APP_DIR="$DRAGONSUITE_ROOT/projects/odysseus"
LOG_FILE="/tmp/odysseus.log"

service_header "$SERVICE_NAME" "$PORT"

if [ ! -d "$APP_DIR" ]; then
    echo "Project not found: $APP_DIR"
    echo "Clone with: git clone https://github.com/pewdiepie-archdaemon/odysseus.git $APP_DIR"
    exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is required for Odysseus."
    exit 1
fi

mkdir -p \
    "$APP_DIR/data" \
    "$APP_DIR/logs" \
    /home/edq/ai_generated/odysseus/generated_images \
    /home/edq/ai_generated/odysseus/gallery \
    /home/edq/ai_generated/odysseus/gallery_uploads

if [ -f "$DRAGONSUITE_ROOT/.env" ]; then
    set -a
    source "$DRAGONSUITE_ROOT/.env"
    set +a
fi

cd "$APP_DIR"
COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.dragonsuite.yml --env-file .env)

if "${COMPOSE[@]}" ps --status running --services | grep -qx "odysseus"; then
    echo "Odysseus is already running."
else
    clear_port "$PORT"
fi

echo "Starting Odysseus with Docker Compose..."
if [ "${ODYSSEUS_REBUILD:-0}" = "1" ] || ! docker image inspect odysseus-odysseus:latest >/dev/null 2>&1; then
    "${COMPOSE[@]}" up -d --build > "$LOG_FILE" 2>&1
else
    "${COMPOSE[@]}" up -d > "$LOG_FILE" 2>&1
fi

echo "Waiting for Odysseus..."
if wait_for_port "$PORT" 180; then
    echo "Odysseus ready at http://192.168.7.226:$PORT"
    echo ""
    echo "First login password, if this is a fresh data directory:"
    "${COMPOSE[@]}" logs --tail=80 odysseus | grep -Ei "password|admin" || true
else
    echo "Odysseus did not respond in time. Recent launcher output:"
    tail -80 "$LOG_FILE" || true
    echo ""
    echo "Recent container logs:"
    "${COMPOSE[@]}" logs --tail=80 odysseus || true
    exit 1
fi
