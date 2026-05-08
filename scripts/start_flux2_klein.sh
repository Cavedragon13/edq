#!/bin/bash
# DragonFlux Klein — FLUX.2-klein Image Generator with LoRA Support
# Port: 8001
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="DragonFlux Klein"
PORT=8001
VENV="venv_flux2"
SCRIPT="scripts/flux2_klein_gradio.py"

service_header "$SERVICE_NAME" "$PORT"
gpu_preflight "$PORT"
activate_venv "$VENV"
set_pytorch_env

mkdir -p "$HOME/ai_generated/flux2-klein"
mkdir -p "$HOME/models/loras/flux-klein"
python - <<'PY'
from huggingface_hub import snapshot_download

for repo_id in [
    "black-forest-labs/FLUX.2-klein-4B",
    "black-forest-labs/FLUX.2-klein-9B",
]:
    snapshot_download(repo_id, local_files_only=True)

print("✓ Local FLUX.2-klein model cache found")
PY

echo "🚀 Starting $SERVICE_NAME..."

if pgrep -f "flux2_klein_gradio.py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup python "$SCRIPT" > /tmp/flux2_klein.log 2>&1 &
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 60; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Service did not start in time — check /tmp/flux2_klein.log"
        tail -10 /tmp/flux2_klein.log
        exit 1
    fi
fi
