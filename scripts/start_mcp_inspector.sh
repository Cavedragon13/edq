#!/bin/bash
set -e

cd /srv/containers/edq

echo "🔍 Starting MCP Inspector..."
echo "   Port: 8020"
echo "   Access: http://192.168.7.226:8020"
echo ""

# Use venv with Supabase
if [ -d "venv_mcp_inspector" ]; then
    echo "✓ Using venv with Supabase integration"
    venv_mcp_inspector/bin/python scripts/mcp_inspector_server.py
else
    echo "⚠️  venv not found, using system Python (no Supabase)"
    python3 scripts/mcp_inspector_server.py
fi
