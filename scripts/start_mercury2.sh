#!/bin/bash
# Mercury2 Diffusion Chat - Start Script
# Starts the web server (port 8036) for Inception Labs Mercury2 API

set -e

echo "⚗️  Starting Mercury2 Diffusion Chat..."
echo ""

# Check API key
source /srv/containers/edq/.env 2>/dev/null || true
if [ -z "$MERCURY2_API_KEY" ]; then
    echo "❌ ERROR: MERCURY2_API_KEY not found in /srv/containers/edq/.env"
    exit 1
fi
echo "✓ Mercury2 API key found"

# Start server if not already running
if pgrep -f "mercury2_server.py" > /dev/null; then
    echo "✓ Mercury2 server already running"
else
    echo "⚙️  Starting Mercury2 server..."
    nohup /usr/bin/python3 /srv/containers/edq/scripts/mercury2_server.py > /tmp/mercury2_server.log 2>&1 &
    sleep 1

    if pgrep -f "mercury2_server.py" > /dev/null; then
        echo "✓ Server started on port 8036"
    else
        echo "❌ Failed to start server"
        tail -10 /tmp/mercury2_server.log
        exit 1
    fi
fi

echo ""
echo "✅ Mercury2 ready"
echo "   Local:  http://localhost:8036"
echo "   LAN:    http://192.168.7.226:8036"
echo "   Model:  mercury-2 (Inception Labs)"
echo "   Feature: Diffusion streaming — watch tokens crystallize"
