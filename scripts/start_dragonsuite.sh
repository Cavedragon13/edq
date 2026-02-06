#!/bin/bash
set -e

# Dragonsuite v2 - Project Dashboard Launcher
# Starts the FastAPI backend on port 8100

BASE_DIR="/srv/containers/edq"
VENV_DIR="$BASE_DIR/venv_dragonsuite"
SCRIPT="$BASE_DIR/scripts/dragonsuite_server.py"

echo "=================================================="
echo "  Dragonsuite v2 - Project Dashboard"
echo "=================================================="
echo ""

# Get local IP
LOCAL_IP=$(hostname -I | awk '{print $1}')
if [ -z "$LOCAL_IP" ]; then
    LOCAL_IP="127.0.0.1"
fi

# Check if venv exists
if [ ! -d "$VENV_DIR" ]; then
    echo "[*] Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    echo "[+] Virtual environment created"
fi

# Activate venv
source "$VENV_DIR/bin/activate"

# Check and install dependencies
echo "[*] Checking dependencies..."

if ! python -c "import fastapi" 2>/dev/null; then
    echo "[*] Installing fastapi..."
    pip install --quiet fastapi
fi

if ! python -c "import uvicorn" 2>/dev/null; then
    echo "[*] Installing uvicorn..."
    pip install --quiet uvicorn
fi

if ! python -c "import qrcode" 2>/dev/null; then
    echo "[*] Installing qrcode[pil]..."
    pip install --quiet "qrcode[pil]"
fi

echo "[+] Dependencies OK"
echo ""

# Display URLs
echo "  Starting dashboard server..."
echo ""
echo "  Local:   http://localhost:8100"
echo "  Network: http://$LOCAL_IP:8100"
echo ""
echo "  Press Ctrl+C to stop"
echo "=================================================="
echo ""

# Start server
cd "$BASE_DIR"
python "$SCRIPT"
