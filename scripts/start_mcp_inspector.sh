#!/bin/bash
# MCP Inspector — Security auditing for MCP servers
# Port: 8020
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="MCP Inspector"
PORT=8020
VENV="venv_mcp_inspector"
SCRIPT="scripts/mcp_inspector_server.py"

service_header "$SERVICE_NAME" "$PORT"
clear_port "$PORT"
activate_venv "$VENV"

echo "🚀 Starting $SERVICE_NAME..."

if pgrep -f "mcp_inspector_server.py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup python "$SCRIPT" > /tmp/mcp_inspector.log 2>&1 &
    if wait_for_port "$PORT" 30; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Failed — check /tmp/mcp_inspector.log"
        tail -10 /tmp/mcp_inspector.log
        exit 1
    fi
fi
