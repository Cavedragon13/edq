#!/bin/bash
# Gemma 4 E4B Chat — Start Script
# Port: 8043  |  No GPU venv  |  Requires Ollama
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="Gemma 4 E4B"
PORT=8043

service_header "$SERVICE_NAME" "$PORT"
clear_port "$PORT"

echo "🔧 Pre-flight checks..."
if ! curl -s http://localhost:11434/api/version > /dev/null 2>&1; then
    echo "❌ Ollama not running — start Ollama first"
    exit 1
fi
echo "✓ Ollama reachable"

if ! ollama list 2>/dev/null | grep -q "gemma4:e4b"; then
    echo "⏳ Pulling gemma4:e4b (9.6 GB)..."
    ollama pull gemma4:e4b
fi
echo "✓ gemma4:e4b present"

echo "🚀 Starting $SERVICE_NAME..."
if pgrep -f "gemma4_server.py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup python3 scripts/gemma4_server.py > /tmp/gemma4_server.log 2>&1 &
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 30; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Service did not start in time — check /tmp/gemma4_server.log"
        tail -10 /tmp/gemma4_server.log
        exit 1
    fi
fi
