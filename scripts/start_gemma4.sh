#!/bin/bash
# Gemma 4 E4B Chat -- Start Script
set -e
echo Starting Gemma 4 E4B...
if ! curl -s http://localhost:11434/api/version > /dev/null 2>&1; then
    echo ERROR: Ollama not running
    exit 1
fi
echo Ollama reachable
if ! ollama list 2>/dev/null | grep -q gemma4:e4b; then
    echo Pulling gemma4:e4b 9.6GB...
    ollama pull gemma4:e4b
fi
echo gemma4:e4b present
if pgrep -f gemma4_server.py > /dev/null; then
    echo Server already running
else
    echo Launching chat server...
    nohup python3 /srv/containers/edq/scripts/gemma4_server.py > /tmp/gemma4_server.log 2>&1 &
    sleep 1
    if pgrep -f gemma4_server.py > /dev/null; then
        echo Server started on port 8043
    else
        echo FAILED -- check /tmp/gemma4_server.log
        exit 1
    fi
fi
echo Gemma 4 E4B ready at http://192.168.7.226:8043
