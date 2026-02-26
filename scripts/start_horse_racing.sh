#!/bin/bash
# Horse Racing v2 Launcher
# Win/Place/Show betting, parlay tickets, AI opponents
# Port: 8030

PROJECT_DIR="/srv/containers/edq/projects/horse-racing-v2"

echo ""
echo "Horse Racing v2"
echo "==============="
echo "Win/Place/Show · Parlay Tickets · AI Opponents"
echo ""

# Kill any stale vite processes for this project before starting
STALE=$(ps aux | grep "horse-racing-v2" | grep -v grep | awk '{print $2}')
if [ -n "$STALE" ]; then
    echo "Stopping stale instance..."
    echo "$STALE" | xargs kill -9 2>/dev/null || true
    sleep 1
fi

# Load nvm so Node 20 is used (required by Vite 7)
export NVM_DIR="/home/edq/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"
nvm use 20 --silent 2>/dev/null || true

cd "$PROJECT_DIR"

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    npm install
fi

echo "Starting on port 8030..."
echo ""
echo "   Local:  http://localhost:8030"
echo "   LAN:    http://192.168.7.226:8030"
echo ""

# Port, host, and strictPort are configured in vite.config.js
exec npm run dev
