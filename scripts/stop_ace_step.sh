#!/bin/bash
# Stop ACE-Step 1.5 XL and its helper worker processes.
set -e

PATTERNS=(
    "ACE-Step-1.5-xl.*start_gradio_ui.sh"
    "uv run .*acestep .*--port 8021"
    "ACE-Step-1.5-xl/.venv/bin/acestep .*--port 8021"
    "ACE-Step-1.5-xl/.venv/bin/python .*acestep .*--port 8021"
    "ACE-Step-1.5-xl/.venv/lib/python.*/site-packages/torch/_inductor/compile_worker"
)

echo "Stopping ACE-Step 1.5 XL..."
for pattern in "${PATTERNS[@]}"; do
    pkill -TERM -f "$pattern" 2>/dev/null || true
done

sleep 3

remaining=0
for pattern in "${PATTERNS[@]}"; do
    if pgrep -f "$pattern" >/dev/null 2>&1; then
        remaining=1
        pkill -KILL -f "$pattern" 2>/dev/null || true
    fi
done

if [ "$remaining" -eq 1 ]; then
    echo "ACE-Step required force cleanup for lingering workers."
else
    echo "ACE-Step stopped cleanly."
fi
