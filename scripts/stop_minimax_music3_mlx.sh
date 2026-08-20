#!/usr/bin/env bash
# Stop MiniMax Music 3 MLX server on odragon.
set -euo pipefail
MAC_HOST="${MINIMAX_MLX_MAC_HOST:-odragon.local}"
ssh -o BatchMode=yes -o ConnectTimeout=8 "edq@${MAC_HOST}" "pkill -f 'mlx-serve serve' || true"
