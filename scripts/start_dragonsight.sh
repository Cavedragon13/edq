#!/bin/bash
# Dragonsight 4 - Start Script
# Starts the web server (port 8080) + checks Ollama dependency

OUTPUT_DIR="$HOME/ai_generated/dragonsight"

echo "🐉 Starting Dragonsight 4..."
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Verify Ollama is responding (runs via snap, auto-starts on boot)
if ! curl -s --max-time 5 http://127.0.0.1:11434/api/tags > /dev/null 2>&1; then
    echo "❌ ERROR: Ollama not responding on port 11434"
    echo "   Ollama should be running via snap (auto-starts on boot)"
    echo "   Check with: snap services ollama"
    exit 1
fi
echo "✓ Ollama ready (qwen3-vl:8b for vision)"

# Start Dragonsight 4 HTTP server (if not already running)
if pgrep -f "dragonsight_server.py" > /dev/null; then
    echo "✓ Dragonsight 4 web server already running"
else
    echo "⚙️  Starting Dragonsight 4 web server..."
    nohup /usr/bin/python3 /srv/containers/edq/scripts/dragonsight_server.py > /tmp/dragonsight_server.log 2>&1 &
    sleep 1
    
    if pgrep -f "dragonsight_server.py" > /dev/null; then
        echo "✓ Web server started on port 8080"
    else
        echo "❌ Failed to start web server"
        tail -5 /tmp/dragonsight_server.log
        exit 1
    fi
fi

echo ""
echo "✅ Dragonsight 4 ready"
echo "   Local:  http://localhost:8080"
echo "   LAN:    http://192.168.7.226:8080"
echo "   Backend: Ollama (qwen3-vl:8b)"
echo "   Output: $OUTPUT_DIR"
