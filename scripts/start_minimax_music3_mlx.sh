#!/usr/bin/env bash
# MiniMax Music 3 — MLX (odragon, Mac Mini M4 Pro)
# Native Zig mlx-serve engine, ~8.8x realtime measured 2026-08-19.
# Model + its tokenizer files (mlx-serve's own pull is missing these upstream
# — see README note) already live in ~/.mlx-serve/models on odragon.
set -euo pipefail
MAC_HOST="${MINIMAX_MLX_MAC_HOST:-odragon.local}"
ssh -o BatchMode=yes -o ConnectTimeout=8 "edq@${MAC_HOST}" \
  "pgrep -f 'mlx-serve serve' > /dev/null || (nohup /opt/homebrew/bin/mlx-serve serve --max-resident-mem 24GB > /tmp/mlx_serve.log 2>&1 & disown)"
