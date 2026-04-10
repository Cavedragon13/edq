#!/bin/bash
set -e

# Dragonweyr - Polymarket Scout + Probability Engine + Execution Server
# Serves HTML frontend, proxies Claude API, wraps py_clob_client
# Port 8046

BASE_DIR="/srv/containers/edq"
VENV_DIR="$BASE_DIR/venv_dragonweyr"
SERVER="$BASE_DIR/projects/dragonweyr/server.py"

echo "=================================================="
echo "  Dragonweyr - Polymarket Scout & Engine"
echo "=================================================="
echo ""

LOCAL_IP=$(hostname -I | awk '{print $1}')
if [ -z "$LOCAL_IP" ]; then
    LOCAL_IP="127.0.0.1"
fi

if [ ! -d "$VENV_DIR" ]; then
    echo "ERROR: venv not found at $VENV_DIR"
    echo "Run: python3 -m venv $VENV_DIR && $VENV_DIR/bin/pip install fastapi uvicorn httpx python-dotenv py-clob-client"
    exit 1
fi

if [ ! -f "$SERVER" ]; then
    echo "ERROR: server.py not found at $SERVER"
    exit 1
fi

echo "  URL:     http://$LOCAL_IP:8046"
echo "  LAN:     http://192.168.7.226:8046"
echo ""
echo "  Scout tab:  browse & filter markets"
echo "  Engine tab: Claude AI probability analysis"
echo "  Ledger tab: paper trade tracking"
echo "  Execute tab: live order execution (requires credentials)"
echo ""

source "$VENV_DIR/bin/activate"
exec python3 "$SERVER"
