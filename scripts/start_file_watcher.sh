#!/bin/bash
set -e

echo "🐉 Starting Dragon File Watcher..."

# Activate venv
source /srv/containers/edq/venv_dragonsuite/bin/activate

# Install watchdog if not present
if ! python -c "import watchdog" 2>/dev/null; then
    echo "📦 Installing watchdog..."
    pip install watchdog requests
fi

# Check if Ollama is running
if ! curl -s http://127.0.0.1:11434/api/tags > /dev/null 2>&1; then
    echo "❌ Ollama is not running!"
    echo "Please ensure Ollama is running on port 11434"
    exit 1
fi

# Run the file watcher
echo "✓ Starting file watcher service..."
python /srv/containers/edq/scripts/file_watcher.py
