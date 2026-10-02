#!/bin/bash
# SAM 2.1 — the Gradio demo (projects/sam2/demo/gradio_app.py) only loads
# sam2.1_hiera_large.pt (sam2.1_hiera_l.yaml config). URL from Meta's own
# projects/sam2/checkpoints/download_ckpts.sh.
set -e
CHECKPOINTS_DIR="/srv/containers/edq/projects/sam2/checkpoints"
CKPT="$CHECKPOINTS_DIR/sam2.1_hiera_large.pt"
URL="https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_large.pt"

mkdir -p "$CHECKPOINTS_DIR"
if [ -f "$CKPT" ]; then
    echo "✓ Already present: $CKPT"
else
    echo "Downloading sam2.1_hiera_large.pt..."
    wget -O "$CKPT" "$URL"
fi
