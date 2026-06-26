#!/usr/bin/env bash
set -euo pipefail
MAC_HOST="${BONSAI_MAC_HOST:-192.168.7.131}"
MAC_DEMO_DIR="${BONSAI_MAC_DEMO_DIR:-/Users/edq/AI/Bonsai-Image-Demo}"
ssh -o BatchMode=yes -o ConnectTimeout=8 "edq@${MAC_HOST}" "cd \"${MAC_DEMO_DIR}\" && BONSAI_VARIANT=ternary BONSAI_FRONTEND_PROD=1 BACKEND_PORT=8040 FRONTEND_PORT=8019 nohup ./scripts/serve.sh > /tmp/bonsai_mlx_studio.log 2>&1 &"
