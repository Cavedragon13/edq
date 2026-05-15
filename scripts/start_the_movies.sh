#!/bin/bash
# The Movies (Working Title) — AI Film Studio Simulation
# Port: 8035
# APIs: Gemini 2.5 Flash, Nano Banana 2, Veo 3.1, Lyria 3
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="The Movies"
PORT=8035
VENV="venv_the_movies"
SCRIPT="scripts/the_movies_server.py"
VENV_PATH="/srv/containers/edq/$VENV"

service_header "$SERVICE_NAME" "$PORT"
clear_port "$PORT"

if [ ! -d "$VENV_PATH" ]; then
    echo "❌ Venv not found at $VENV_PATH"
    echo "   Create it and install dependencies before launch; do not install on first run."
    exit 1
fi

echo "📦 Checking dependencies..."
"$VENV_PATH/bin/python" - <<'PY'
import importlib.util
missing = [
    name for name in ("google.genai", "fastapi", "uvicorn", "dotenv")
    if importlib.util.find_spec(name) is None
]
if missing:
    raise SystemExit(
        "Missing dependencies in venv_the_movies: "
        + ", ".join(missing)
        + "\nInstall them outside the launcher, then retry."
    )
PY

activate_venv "$VENV"

echo "🚀 Starting $SERVICE_NAME..."

if pgrep -f "the_movies_server.py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup python "$SCRIPT" > /tmp/the_movies.log 2>&1 &
    if wait_for_port "$PORT" 30; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
        echo "   APIs: Gemini 2.5 Flash · Nano Banana 2 · Veo 3.1 fast · Lyria 3"
    else
        echo "❌ Failed — check /tmp/the_movies.log"
        tail -10 /tmp/the_movies.log
        exit 1
    fi
fi
