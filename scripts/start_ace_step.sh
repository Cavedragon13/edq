#!/bin/bash
# ACE-Step 1.5 XL Music Generation
# Port: 8021
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="ACE-Step 1.5 XL"
PORT=8021
ACE_HOME="$DRAGONSUITE_ROOT/projects/ACE-Step-1.5-xl"
ACE_CHECKPOINTS_DIR="$ACE_HOME/checkpoints"

service_header "$SERVICE_NAME" "$PORT"
if [ ! -d "$ACE_CHECKPOINTS_DIR/acestep-v15-xl-turbo" ]; then
    echo "❌ ACE-Step XL checkpoints not found at $ACE_CHECKPOINTS_DIR"
    echo "   Expected: $ACE_CHECKPOINTS_DIR/acestep-v15-xl-turbo"
    exit 1
fi

export ACESTEP_CHECKPOINTS_DIR="$ACE_CHECKPOINTS_DIR"
gpu_preflight "$PORT"
set_pytorch_env

echo "🚀 Starting $SERVICE_NAME..."
if ss -tlnp | grep -q ":${PORT} "; then
    echo "✓ Already running on port $PORT"
else
    # CHECK_UPDATE=false disables the interactive update prompt that blocks headless/background launches
    nohup bash -c 'cd /srv/containers/edq/projects/ACE-Step-1.5-xl && CHECK_UPDATE=false bash ./start_gradio_ui.sh' > /tmp/ace_step_xl.log 2>&1 &
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 1800; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Service did not start in time — check /tmp/ace_step_xl.log"
        tail -10 /tmp/ace_step_xl.log
        exit 1
    fi
fi
