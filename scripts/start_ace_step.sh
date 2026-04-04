#!/bin/bash
# ACE-Step 1.5 Music Generation
# Port: 8021 | uv run (self-managed env, no venv activation)
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="ACE-Step 1.5"
PORT=8021

service_header "$SERVICE_NAME" "$PORT"
gpu_preflight "$PORT"
set_pytorch_env

echo "🚀 Starting $SERVICE_NAME..."
if pgrep -f "acestep" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup bash -c 'cd /srv/containers/edq/projects/ACE-Step-1.5 && uv run acestep \
      --port 8021 \
      --server-name 0.0.0.0 \
      --language en \
      --config_path acestep-v15-turbo \
      --lm_model_path acestep-5Hz-lm-1.7B \
      --init_service true' > /tmp/ace_step.log 2>&1 &
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 60; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Service did not start in time — check /tmp/ace_step.log"
        tail -10 /tmp/ace_step.log
        exit 1
    fi
fi
