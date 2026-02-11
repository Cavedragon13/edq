#!/bin/bash
set -e

cd /srv/containers/edq

echo "🔍 Starting MCP Inspector..."
echo "   Port: 8020"
echo "   Access: http://192.168.7.226:8020"
echo ""

python3 scripts/mcp_inspector_server.py
