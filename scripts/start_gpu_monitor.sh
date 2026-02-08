#!/bin/bash
# Launch GPU Monitor - Minimal floating GPU stats display
# Port: 8015

set -e

cd /srv/containers/edq

echo "🎮 Starting GPU Monitor..."
python3 scripts/gpu_monitor_server.py
