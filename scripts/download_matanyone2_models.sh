#!/bin/bash
# Pre-download all MatAnyone 2 models and test samples
# Eliminates first-launch wait time
# Per SOP: models must be present BEFORE first run

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
APP_DIR="$PROJECT_DIR/projects/matanyone2"
CHECKPOINTS_DIR="$APP_DIR/pretrained_models"
TEST_SAMPLES_DIR="$APP_DIR/hugging_face/test_sample"

echo "✂️  MatAnyone 2 — Pre-downloading models"
echo "=========================================="
mkdir -p "$CHECKPOINTS_DIR"
mkdir -p "$TEST_SAMPLES_DIR"

# Helper: download with aria2c (resumable, fast) or fallback to wget
download() {
    local url="$1"
    local dest="$2"
    local filename
    filename=$(basename "$dest")

    if [ -f "$dest" ]; then
        echo "  ✅ Already present: $filename"
        return 0
    fi

    echo "  📥 Downloading: $filename"
    if command -v aria2c &>/dev/null; then
        aria2c --split=4 --max-connection-per-server=4 --dir="$(dirname "$dest")" \
               --out="$filename" --continue=true --quiet "$url"
    else
        wget -q --show-progress -O "$dest" "$url"
    fi
    echo "  ✅ Done: $filename ($(du -sh "$dest" | cut -f1))"
}

echo ""
echo "--- SAM vit_h checkpoint (~2.5GB) ---"
download \
    "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_4b8939.pth" \
    "$CHECKPOINTS_DIR/sam_vit_h_4b8939.pth"

echo ""
echo "--- MatAnyone 2 weights (~0.5GB) ---"
download \
    "https://github.com/pq-yang/MatAnyone2/releases/download/v1.0.0/matanyone2.pth" \
    "$CHECKPOINTS_DIR/matanyone2.pth"

echo ""
echo "--- MatAnyone 1 weights (needed by app) ---"
download \
    "https://github.com/pq-yang/MatAnyone/releases/download/v1.0.0/matanyone.pth" \
    "$CHECKPOINTS_DIR/matanyone.pth"

echo ""
echo "--- Test sample videos ---"
for sample in \
    "test-sample-0-1080p.mp4" \
    "test-sample-1-1080p.mp4" \
    "test-sample-2-720p.mp4" \
    "test-sample-3-720p.mp4" \
    "test-sample-4-720p.mp4" \
    "test-sample-5-720p.mp4"; do
    download \
        "https://github.com/pq-yang/MatAnyone2/releases/download/media/$sample" \
        "$TEST_SAMPLES_DIR/$sample"
done

echo ""
echo "✅ All MatAnyone 2 assets downloaded."
echo "   Launch with: bash scripts/start_matanyone2.sh"
