#!/bin/bash
# Gemma 4 E4B Chat — Start Script (uncensored: OBLITERATUS/gemma-4-E4B-it-OBLITERATED)
# Port: 8043  |  Dedicated venv  |  Requires Ollama
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="Gemma 4 E4B"
PORT=8043
VENV="venv_gemma4"
HF_MODEL="hf.co/OBLITERATUS/gemma-4-E4B-it-OBLITERATED:Q5_K_M"
LOCAL_TAG="gemma4-obliterated"

service_header "$SERVICE_NAME" "$PORT"
clear_port "$PORT"
activate_venv "$VENV"

echo "🔧 Pre-flight checks..."
if ! curl -s http://localhost:11434/api/version > /dev/null 2>&1; then
    echo "❌ Ollama not running — start Ollama first"
    exit 1
fi
echo "✓ Ollama reachable"

if ! ollama list 2>/dev/null | grep -q "$LOCAL_TAG"; then
    if ollama list 2>/dev/null | grep -q "${HF_MODEL%:Q5_K_M}"; then
        echo "⏳ Creating local alias $LOCAL_TAG..."
        ollama cp "$HF_MODEL" "$LOCAL_TAG"
    else
        echo "⏳ Pulling $HF_MODEL (~6 GB)..."
        ollama pull "$HF_MODEL"
        echo "⏳ Creating local alias $LOCAL_TAG..."
        ollama cp "$HF_MODEL" "$LOCAL_TAG"
    fi
fi
echo "✓ $LOCAL_TAG present"

echo "🚀 Starting $SERVICE_NAME..."
if pgrep -f "gemma4_server.py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup "$VIRTUAL_ENV/bin/python" scripts/gemma4_server.py > /tmp/gemma4_server.log 2>&1 &
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 30; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Service did not start in time — check /tmp/gemma4_server.log"
        tail -10 /tmp/gemma4_server.log
        exit 1
    fi
fi
