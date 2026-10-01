#!/bin/bash
# Mira Scene — full single-image-to-3D-scene pipeline (SAM3 + Gemini, depth, CCM, SAM-3D, floor, scene, environment)
# Port: 8071. The web server holds no VRAM itself; each job runs scripts/run_mira_pipeline.sh, whose
# stages use the GPU one at a time (peak ~14.5GB), so the gate below reserves that for a job.
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

TOOL_NAME="mira-scene"
REQ_VRAM_MIB=14500
REQ_RAM_MIB=12000
source scripts/vram_guard.sh

SERVICE_NAME="Mira Scene"
PORT=8071
PYTHON_BIN="$DRAGONSUITE_ROOT/conda_envs/mira-sam3d/bin/python3.11"

service_header "$SERVICE_NAME" "$PORT"

# Fail fast on missing pieces (download: scripts/download_mira_scene_models.sh, download_mira_stage_models.sh)
if [ ! -x "$PYTHON_BIN" ]; then
  echo "❌ Mira Python runtime not found: $PYTHON_BIN"
  exit 1
fi
if [ ! -f "$DRAGONSUITE_ROOT/models/mira-scene/pipeline/model_index.json" ] || [ ! -f "$DRAGONSUITE_ROOT/models/mira-scene/stages/sam3/sam3.pt" ]; then
  echo "❌ Mira models missing — run: bash scripts/download_mira_scene_models.sh && bash scripts/download_mira_stage_models.sh"
  exit 1
fi
if ! grep -q '^GOOGLE_API_KEY=.' "$DRAGONSUITE_ROOT/.env"; then
  echo "❌ GOOGLE_API_KEY missing from $DRAGONSUITE_ROOT/.env (Mira uses Gemini for scene understanding)"
  exit 1
fi

vram_preflight || exit 1
clear_port "$PORT"
mkdir -p /home/edq/ai_generated/mira-scene

setsid nohup "$PYTHON_BIN" "$DRAGONSUITE_ROOT/scripts/mira_scene_server.py" < /dev/null > /tmp/mira_scene.log 2>&1 &
register_tool $!
if wait_for_port "$PORT" 60; then
  echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
else
  echo "❌ Not up in time — check /tmp/mira_scene.log"
  tail -40 /tmp/mira_scene.log
  exit 1
fi
