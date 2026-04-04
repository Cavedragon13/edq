#!/bin/bash
# Dragon File Watcher — Background daemon for file change detection
# No port (background daemon)
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="Dragon File Watcher"
VENV="venv_dragonsuite"
SCRIPT="scripts/file_watcher.py"

service_header "$SERVICE_NAME" ""
activate_venv "$VENV"

# Install watchdog if not present
if ! python -c "import watchdog" 2>/dev/null; then
    echo "📦 Installing watchdog..."
    pip install watchdog requests
fi

# Check if Ollama is running
if ! curl -s http://127.0.0.1:11434/api/tags > /dev/null 2>&1; then
    echo "❌ Ollama is not running!"
    echo "   Please ensure Ollama is running on port 11434"
    exit 1
fi

echo "🚀 Starting $SERVICE_NAME..."
python "$SCRIPT"
