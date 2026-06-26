#!/usr/bin/env bash
set -euo pipefail

PORT="${KREA2_PORT:-8062}"
PIDS="$(lsof -ti "tcp:${PORT}" 2>/dev/null || true)"
if [[ -z "${PIDS}" ]]; then
  pkill -f "/srv/containers/edq/krea2/krea2_runner.py" 2>/dev/null || true
  exit 0
fi

kill ${PIDS} 2>/dev/null || true
sleep 1
PIDS="$(lsof -ti "tcp:${PORT}" 2>/dev/null || true)"
if [[ -n "${PIDS}" ]]; then
  kill -9 ${PIDS} 2>/dev/null || true
fi
