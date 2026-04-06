#!/bin/bash
set -e
VENV="/srv/containers/edq/venv_dragonsheet"
BACKEND="/srv/containers/edq/projects/dragonsheet/backend"
FRONTEND="/srv/containers/edq/projects/dragonsheet/frontend"
PORT=8044

# Check venv exists
if [ ! -d "$VENV" ]; then
    echo "❌ venv_dragonsheet not found."
    echo "   Run first: bash /srv/containers/edq/projects/dragonsheet/scripts/setup_dragonsheet.sh"
    exit 1
fi

# Check frontend is built
if [ ! -f "$FRONTEND/dist/index.html" ]; then
    echo "⚠ Frontend not built — building now..."
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"
    cd "$FRONTEND"
    npm run build
fi

source "$VENV/bin/activate"

echo "🐉 DragonSheet starting on port $PORT..."
echo "   Access: http://192.168.7.226:$PORT"
echo ""

cd "$BACKEND"
exec uvicorn dragonsheet_server:app --host 0.0.0.0 --port "$PORT"
