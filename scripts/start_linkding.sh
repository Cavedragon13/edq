#!/bin/bash
set -e

# Linkding bookmark manager launcher (port 8039)
# Self-hosted cross-browser bookmark sync

BASE_DIR="/srv/containers/edq"
COMPOSE_FILE="$BASE_DIR/docker/linkding/docker-compose.yml"
DATA_DIR="$BASE_DIR/media/linkding_data"

echo "=================================================="
echo "  Linkding Bookmark Manager"
echo "=================================================="
echo ""

LOCAL_IP=$(hostname -I | awk '{print $1}')
if [ -z "$LOCAL_IP" ]; then
    LOCAL_IP="127.0.0.1"
fi

# Load env for password
source "$BASE_DIR/.env"

# Create data dir if needed
mkdir -p "$DATA_DIR"

# Pull latest if not already present
if ! docker image inspect sissbruecker/linkding:latest &>/dev/null; then
    echo "[*] Pulling linkding image..."
    docker pull sissbruecker/linkding:latest
fi

# Start
echo "[*] Starting Linkding..."
docker compose -f "$COMPOSE_FILE" --env-file "$BASE_DIR/.env" up -d

echo ""
echo "  Local:   http://localhost:8039"
echo "  Network: http://$LOCAL_IP:8039"
echo ""
echo "  Login: edq / (see .env LD_SUPERUSER_PASSWORD)"
echo ""
echo "  Press Ctrl+C to view logs, or run:"
echo "  docker compose -f $COMPOSE_FILE logs -f"
echo "=================================================="
