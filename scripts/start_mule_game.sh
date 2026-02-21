#!/bin/bash
set -e

# M.U.L.E. Game Launcher
# Port: 8016
# A tribute to Dani Bunten Berry
# Served as standalone HTML5 game (no Gradio needed)

MEDIA_DIR="/srv/containers/edq/media"
PORT=8016

echo "🌌 Starting M.U.L.E. - Planet Irata..."
echo "🫐 Featuring Bunten Berries - tribute to Dani Bunten Berry"

if [ ! -f "$MEDIA_DIR/mule_game.html" ]; then
    echo "❌ mule_game.html not found at $MEDIA_DIR"
    exit 1
fi

echo "🚀 Launching on http://192.168.7.226:${PORT}"
echo "   Open: http://192.168.7.226:${PORT}/mule_game.html"
echo ""
echo "   Ctrl+C to stop"

cd "$MEDIA_DIR"
exec python3 -m http.server "$PORT" --bind 0.0.0.0
