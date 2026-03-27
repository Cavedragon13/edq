#!/bin/bash
# start_dragonglass.sh — DragonGlass (port 8040)
# Street View scout + Gemini image transform
set -e

VENV="/srv/containers/edq/venv_streetview"
SCRIPT="/srv/containers/edq/scripts/dragonglass.py"

source "$VENV/bin/activate"

echo "◆  DragonGlass"
echo "==============="
echo "Local:  http://localhost:8040"
echo "LAN:    http://192.168.7.226:8040"
echo ""
echo "Press Ctrl+C to stop"
echo ""

exec python3 "$SCRIPT"
