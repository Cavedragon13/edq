#!/bin/bash
# Z-Image Base — Alibaba Tongyi 6B Text-to-Image
# Port: 8011
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="Z-Image Base"
PORT=8011
VENV="venv_zimage"
SCRIPT="scripts/zimage_base_gradio.py"

service_header "$SERVICE_NAME" "$PORT"
gpu_preflight "$PORT"
activate_venv "$VENV"
set_pytorch_env

echo "🚀 Starting $SERVICE_NAME..."
mkdir -p "$HOME/ai_generated/zimage"

python - <<'PY'
from huggingface_hub import hf_hub_download, snapshot_download

required_snapshots = [
    "Tongyi-MAI/Z-Image",
    "Tongyi-MAI/Z-Image-Turbo",
]

for repo_id in required_snapshots:
    snapshot_download(repo_id, local_files_only=True)

hf_hub_download(
    repo_id="alibaba-pai/Z-Image-Turbo-Fun-Controlnet-Union-2.1",
    filename="Z-Image-Turbo-Fun-Controlnet-Union-2.1.safetensors",
    local_files_only=True,
)

print("✓ Local Z-Image model cache found")
PY

if pgrep -f "zimage_base_gradio.py" > /dev/null; then
    if curl -s --max-time 2 "http://127.0.0.1:$PORT/" > /dev/null 2>&1; then
        echo "✓ Already running on port $PORT"
    else
        echo "⚠️  Found stale Z-Image process without a listening port; stopping it..."
        pkill -f "zimage_base_gradio.py" || true
        sleep 2
        nohup python "$SCRIPT" > /tmp/zimage.log 2>&1 &
        echo "⏳ Waiting for service..."
        if wait_for_port "$PORT" 30; then
            echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
        else
            echo "❌ Service did not start in time — check /tmp/zimage.log"
            tail -10 /tmp/zimage.log
            exit 1
        fi
    fi
else
    nohup python "$SCRIPT" > /tmp/zimage.log 2>&1 &
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 30; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Service did not start in time — check /tmp/zimage.log"
        tail -10 /tmp/zimage.log
        exit 1
    fi
fi
