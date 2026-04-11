#!/bin/bash
set -e

# Dragonweyr-Kalshi — Kalshi Scout + AI Engine + Execution Server
# Port 8047
#
# Required in .env for live execution:
#   KALSHI_API_KEY_ID      — your Kalshi API key ID
#   KALSHI_PRIVATE_KEY_PEM — RSA private key PEM (newlines as \n)
#
# Optional in .env:
#   KALSHI_USE_DEMO=true   — use demo.kalshi.co instead of production

BASE_DIR="/srv/containers/edq"
VENV_DIR="$BASE_DIR/venv_kalshi"
SERVER="$BASE_DIR/projects/kalshi/server.py"

echo "=================================================="
echo "  Dragonweyr — Kalshi Market Engine"
echo "=================================================="
echo ""

LOCAL_IP=$(hostname -I | awk '{print $1}')
if [ -z "$LOCAL_IP" ]; then
    LOCAL_IP="127.0.0.1"
fi

if [ ! -d "$VENV_DIR" ]; then
    echo "ERROR: venv not found at $VENV_DIR"
    echo "Run: python3 -m venv $VENV_DIR && $VENV_DIR/bin/pip install fastapi uvicorn httpx python-dotenv kalshi_python_sync"
    exit 1
fi

if [ ! -f "$SERVER" ]; then
    echo "ERROR: server.py not found at $SERVER"
    exit 1
fi

echo "  URL:     http://$LOCAL_IP:8047"
echo "  LAN:     http://192.168.7.226:8047"
echo ""
echo "  Scout:   Browse & filter Kalshi markets"
echo "  Engine:  Claude AI probability analysis"
echo "  Ledger:  Paper trade tracking"
echo "  Execute: Live order placement (requires KALSHI_API_KEY_ID)"
echo ""
echo "  Credentials:"
source "$BASE_DIR/.env" 2>/dev/null || true
if [ -n "$KALSHI_API_KEY_ID" ]; then
    echo "    API Key:  ${KALSHI_API_KEY_ID:0:8}..."
    if [ "${KALSHI_USE_DEMO:-}" = "true" ]; then
        echo "    API Host: demo.kalshi.co (DEMO)"
    else
        echo "    API Host: api.elections.kalshi.com (PRODUCTION)"
    fi
else
    echo "    No credentials — DEMO MODE (public endpoints only)"
fi
echo ""

source "$VENV_DIR/bin/activate"
exec python3 "$SERVER"
