#!/bin/bash
# Stop Battle Cars by the port it listens on (no process-name matching).
PORT=8069
pids=$(lsof -ti ":$PORT" 2>/dev/null || true)
if [ -n "$pids" ]; then
    echo "$pids" | xargs kill -TERM 2>/dev/null || true
    sleep 1
fi
if lsof -ti ":$PORT" >/dev/null 2>&1; then
    echo "Battle Cars still listening on $PORT"
    exit 1
fi
echo "Battle Cars stopped"
