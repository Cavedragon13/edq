#!/usr/bin/env bash
set -euo pipefail
MAC_HOST="${BONSAI_MAC_HOST:-192.168.7.131}"
ssh -o BatchMode=yes -o ConnectTimeout=8 "edq@${MAC_HOST}" "lsof -tiTCP:3000 -sTCP:LISTEN | xargs kill 2>/dev/null || true; lsof -tiTCP:8000 -sTCP:LISTEN | xargs kill 2>/dev/null || true; pkill -f '/Users/edq/AI/Bonsai-Image-Demo.*serve.sh' || true"
