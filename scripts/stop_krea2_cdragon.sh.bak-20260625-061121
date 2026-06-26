#!/usr/bin/env bash
set -euo pipefail
MAC_HOST="${BONSAI_MAC_HOST:-192.168.7.131}"
MAC_DEMO_DIR="${BONSAI_MAC_DEMO_DIR:-/Users/edq/AI/Bonsai-Image-Demo}"
ssh -o BatchMode=yes -o ConnectTimeout=8 "edq@${MAC_HOST}" "lsof -tiTCP:8019 -sTCP:LISTEN | xargs kill 2>/dev/null || true; lsof -tiTCP:8040 -sTCP:LISTEN | xargs kill 2>/dev/null || true; pkill -f '/Users/edq/AI/Bonsai-Image-Demo.*serve.sh' || true"
rsync -az -e "ssh -o BatchMode=yes -o ConnectTimeout=8" "edq@${MAC_HOST}:${MAC_DEMO_DIR}/outputs/" /home/edq/ai_generated/bonsai/ || true
