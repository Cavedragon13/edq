#!/bin/bash

echo "=== MCP Configuration Diagnostics ==="
echo ""

echo "1. Checking .mcp.json location:"
if [ -f "/srv/containers/edq/.mcp.json" ]; then
    echo "   ✓ Found at /srv/containers/edq/.mcp.json"
    echo "   Size: $(wc -c < /srv/containers/edq/.mcp.json) bytes"
else
    echo "   ✗ NOT FOUND at /srv/containers/edq/.mcp.json"
fi
echo ""

echo "2. Checking .mcp.json validity:"
if python3 -m json.tool /srv/containers/edq/.mcp.json > /dev/null 2>&1; then
    echo "   ✓ Valid JSON"
else
    echo "   ✗ INVALID JSON - this will break MCP loading!"
fi
echo ""

echo "3. Checking MCP server executables:"
for server in dragonsuite vocab-translator; do
    python_path="/srv/containers/edq/mcp-servers/$server/venv/bin/python"
    server_path="/srv/containers/edq/mcp-servers/$server/server.py"

    if [ -f "$python_path" ]; then
        echo "   ✓ $server Python: $python_path"
    else
        echo "   ✗ $server Python NOT FOUND: $python_path"
    fi

    if [ -f "$server_path" ]; then
        echo "   ✓ $server Server: $server_path"
    else
        echo "   ✗ $server Server NOT FOUND: $server_path"
    fi
done
echo ""

echo "4. Checking environment variables:"
source ~/.bashrc 2>/dev/null
for var in GITHUB_PERSONAL_ACCESS_TOKEN BRAVE_API_KEY SENTRY_AUTH_TOKEN; do
    if [ -n "${!var}" ]; then
        echo "   ✓ $var is set"
    else
        echo "   ✗ $var NOT SET"
    fi
done
echo ""

echo "5. Checking npx availability:"
if command -v npx &> /dev/null; then
    echo "   ✓ npx found at $(which npx)"
else
    echo "   ✗ npx NOT FOUND - needed for playwright, github, etc."
fi
echo ""

echo "6. Testing dragonsuite MCP server:"
if [ -f "/srv/containers/edq/mcp-servers/dragonsuite/venv/bin/python" ]; then
    timeout 3 /srv/containers/edq/mcp-servers/dragonsuite/venv/bin/python /srv/containers/edq/mcp-servers/dragonsuite/server.py --version 2>&1 | head -5 || echo "   (Server doesn't support --version, that's OK)"
fi
echo ""

echo "7. Recommended next steps:"
echo "   - Close VSCode completely (all windows)"
echo "   - Launch VSCode using: code-with-env /srv/containers/edq"
echo "   - Wait 10-15 seconds for MCP servers to initialize"
echo "   - Check Claude Code panel for MCP server status"
echo ""
