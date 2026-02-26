#!/bin/bash
set -e

PORT=8029
VENV="/srv/containers/edq/venv_dragonsong"
SERVER="/srv/containers/edq/scripts/dragonsong_server.py"

echo "🎵 Dragonsong - Lyria RealTime Music"
echo "======================================"

# Create venv if needed
if [ ! -d "$VENV" ]; then
  echo "Creating venv at $VENV..."
  python3 -m venv "$VENV"
fi

# Install/upgrade deps
"$VENV/bin/pip" install -q --upgrade google-genai fastapi uvicorn python-dotenv

echo "Starting on http://0.0.0.0:$PORT"
echo "Access: http://192.168.7.226:$PORT"
exec "$VENV/bin/python" "$SERVER"
