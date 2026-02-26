#!/bin/bash
# Interactive Games - Survival decision series + Selene Lunar Reckoning
set -e
cd /srv/containers/edq/projects/interactive-games

echo "🎮 Interactive Games"
echo "   Port:   8031"
echo "   Access: http://192.168.7.226:8031"
echo "   Live:   https://cavedragon13.github.io/interactive-games/"
echo ""
exec python3 -m http.server 8031
