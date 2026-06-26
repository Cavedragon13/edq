#!/usr/bin/env bash
set -euo pipefail

MAC_HOST="${KREA2_MAC_HOST:-cdragon.local}"
MAC_PORT="${KREA2_PORT:-8062}"
MAC_PROJECT_DIR="${KREA2_PROJECT_DIR:-/Users/edq/Library/Mobile Documents/com~apple~CloudDocs/Downloads/1Projects/krea2-local}"

remote_cmd=$(printf 'cd %q && KREA2_HOST=0.0.0.0 KREA2_PORT=%q nohup ./start_krea2_runner.sh > /tmp/krea2_runner.log 2>&1 &' "${MAC_PROJECT_DIR}" "${MAC_PORT}")
ssh -o BatchMode=yes -o ConnectTimeout=8 "${MAC_HOST}" "${remote_cmd}"
