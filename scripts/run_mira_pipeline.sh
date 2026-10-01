#!/bin/bash
# Run the upstream Mira-Scene pipeline (segmentation -> depth -> CCM -> mesh -> floor -> scene -> environment).
# Usage: bash scripts/run_mira_pipeline.sh <input_image_or_dir> <output_dir> [extra pipeline.py args...]
# Gemini is used for the VLM stages; the key is read from the central .env and never printed.
set -e
cd /srv/containers/edq

if [ "$#" -lt 2 ]; then
  echo "usage: $0 <input_image_or_dir> <output_dir> [pipeline.py args]"
  exit 2
fi
INPUT="$1"
OUTPUT="$2"
shift 2

GOOGLE_KEY_LINE=$(grep -m1 '^GOOGLE_API_KEY=' /srv/containers/edq/.env || true)
if [ -z "$GOOGLE_KEY_LINE" ]; then
  echo "❌ GOOGLE_API_KEY missing from /srv/containers/edq/.env"
  exit 1
fi
export CODEX_API_KEY="${GOOGLE_KEY_LINE#GOOGLE_API_KEY=}"
export MIRA_IMAGE_BACKEND=gemini
export MIRA_IMAGE_MODEL="${MIRA_IMAGE_MODEL:-gemini-3.1-flash-image}"
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export PYTHONPATH="/srv/containers/edq/projects/MoGe:/srv/containers/edq/projects/sam-3d-objects:${PYTHONPATH:-}"
export LIDRA_SKIP_INIT=true
# 16GB GPU: SAM-3D stage 2 keeps weights on the CPU and moves each to the GPU only while in use
# (patch in Mira-Scene/infer_scripts/utils/sam3d_utils.py).
export MIRA_LOW_VRAM=1

exec /srv/containers/edq/conda_envs/mira-geometry/bin/python \
  /srv/containers/edq/projects/Mira-Scene/infer_scripts/pipeline.py \
  --input "$INPUT" --output "$OUTPUT" \
  --config /srv/containers/edq/projects/Mira-Scene/infer_scripts/config/local.yaml "$@"
