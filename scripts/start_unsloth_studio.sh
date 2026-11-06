#!/bin/bash
# Unsloth Studio — LLM fine-tuning web UI
# Port: 8050
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

# Honest footprint — measured 2026-11-06. The bare `studio` subcommand (no
# `run`) starts only the backend web server; it loads no model until the
# user picks one from inside the UI, so idle launch footprint is ~0 VRAM /
# ~700MB RAM. Whatever model the user loads afterward is unbounded by
# design (their choice from any HF repo) and is NOT covered by this gate —
# it only protects the launch itself from co-residing with other heavy jobs.
TOOL_NAME="unsloth-studio"
REQ_VRAM_MIB=1024
REQ_RAM_MIB=2048
source scripts/vram_guard.sh

SERVICE_NAME="Unsloth Studio"
PORT=8050
VENV="venv_unsloth_studio"
LOG="/tmp/unsloth_studio.log"

service_header "$SERVICE_NAME" "$PORT"

vram_preflight || exit 1
clear_port "$PORT"
activate_venv "$VENV"

echo "🚀 Starting $SERVICE_NAME..."
if pgrep -f "studio/backend/run.py" > /dev/null && ss -ltn "( sport = :$PORT )" | grep -q LISTEN; then
    echo "✓ Already running on port $PORT"
else
    nohup unsloth studio -H 0.0.0.0 -p "$PORT" > "$LOG" 2>&1 &
    if wait_for_port "$PORT" 60; then
        server_pid="$(pgrep -f 'studio/backend/run.py' | head -1)"
        [ -n "$server_pid" ] && register_tool "$server_pid"
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Failed — check $LOG"
        tail -20 "$LOG"
        exit 1
    fi
fi
