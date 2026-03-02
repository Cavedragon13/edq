#!/bin/bash
set -e

# The Movies (Working Title) — AI Film Studio Simulation
# Port: 8035
# APIs: Gemini 2.5 Flash, Nano Banana 2, Veo 3.1, Lyria 3

PORT=8035
VENV="/srv/containers/edq/venv_the_movies"
SERVER="/srv/containers/edq/scripts/the_movies_server.py"

echo "🎬 The Movies (Working Title)"
echo "=============================="
echo "AI-powered film studio simulation"
echo "APIs: Gemini 2.5 Flash · Nano Banana 2 · Veo 3.1 · Lyria 3"
echo ""

# Create venv if needed
if [ ! -d "$VENV" ]; then
  echo "📦 Creating venv at $VENV..."
  python3 -m venv "$VENV"
fi

# Install / upgrade dependencies
echo "📦 Checking dependencies..."
"$VENV/bin/pip" install -q --upgrade \
  google-genai \
  fastapi \
  uvicorn \
  python-dotenv

echo "🚀 Starting on http://0.0.0.0:$PORT"
echo "   Access: http://192.168.7.226:$PORT"
echo ""
echo "   Ctrl+C to stop"
echo ""

exec "$VENV/bin/python" "$SERVER"
