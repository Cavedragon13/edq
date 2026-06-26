#!/usr/bin/env bash
set -euo pipefail

cd /srv/containers/edq/krea2
export KREA2_HOME=/srv/containers/edq/krea2
export KREA2_HOST="${KREA2_HOST:-0.0.0.0}"
export KREA2_PORT="${KREA2_PORT:-8062}"
export KREA2_SD_CLI=/srv/containers/edq/krea2/src/stable-diffusion.cpp/build-cuda/bin/sd-cli
export KREA2_OUTPUT_DIR=/home/edq/ai_generated/krea2
export KREA2_LOG_DIR=/srv/containers/edq/krea2/logs
export KREA2_BACKEND="${KREA2_BACKEND:-}"

nohup /srv/containers/edq/venv_dragonsuite/bin/python /srv/containers/edq/krea2/krea2_runner.py > /tmp/krea2_cuda_runner.log 2>&1 &
