#!/bin/bash
set -e

# M.U.L.E. Game Launcher
# Port: 8016
# A tribute to Dani Bunten Berry

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="/srv/containers/edq/projects/mule-game"
VENV_DIR="/srv/containers/edq/venv_mule_game"

echo "🌌 Starting M.U.L.E. - Planet Irata..."
echo "🫐 Featuring Bunten Berries - tribute to Dani Bunten Berry"

# Check if venv exists
if [ ! -d "$VENV_DIR" ]; then
    echo "❌ Virtual environment not found at $VENV_DIR"
    echo "Please run the setup first."
    exit 1
fi

# Activate virtual environment
source "$VENV_DIR/bin/activate"

# Change to project directory
cd "$PROJECT_DIR"

# Launch the Gradio app
echo "🚀 Launching on http://192.168.7.226:8016"
python mule_game_web.py
