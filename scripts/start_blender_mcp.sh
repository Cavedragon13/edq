#!/bin/bash

echo "🎨 Starting Blender MCP Server..."

# Check if Blender is already running
if pgrep -f "blender.*background.*blender_mcp_startup" > /dev/null; then
    echo "⚠️ Blender MCP is already running"
    exit 0
fi

# Start Blender in background with MCP addon
echo "✓ Launching Blender in headless mode..."
echo "✓ MCP addon will listen on localhost:9876"

BLENDER_BIN="$(command -v blender || true)"
if [ -z "$BLENDER_BIN" ] && [ -x /snap/bin/blender ]; then
    BLENDER_BIN="/snap/bin/blender"
fi

if [ -z "$BLENDER_BIN" ]; then
    echo "❌ Blender executable not found"
    exit 1
fi

# Run Blender in background with the MCP startup script
"$BLENDER_BIN" --background \
    --python-use-system-env \
    --python /srv/containers/edq/scripts/blender_mcp_startup.py \
    > /tmp/blender_mcp.log 2>&1 &

BLENDER_PID=$!

# Give it a moment to start
sleep 2

# Quick check if process is still alive
if kill -0 $BLENDER_PID 2>/dev/null; then
    echo "✓ Blender MCP server started (PID: $BLENDER_PID)"
    echo "📍 Listening on localhost:9876"
    echo "📝 Logs: /tmp/blender_mcp.log"
else
    echo "❌ Blender failed to start"
    tail -20 /tmp/blender_mcp.log 2>&1 || echo "No log available"
    exit 1
fi
