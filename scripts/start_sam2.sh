#!/bin/bash
# SAM 2.1 - Segment Anything Model 2
# Image and Video Segmentation by Meta
# Port 8005, LAN accessible

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SAM2_DIR="$PROJECT_DIR/projects/sam2"
VENV_DIR="$PROJECT_DIR/venv_sam2"
CHECKPOINTS_DIR="$SAM2_DIR/checkpoints"
OUTPUT_DIR="$HOME/ai_generated/sam2"

echo "🎯 SAM 2.1 - Segment Anything"
echo "============================="
echo "Meta's Foundation Model for Image & Video Segmentation"
echo ""

# Check for CUDA
if command -v nvidia-smi &> /dev/null; then
    echo "🎮 GPU Info:"
    nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader 2>/dev/null || echo "  (nvidia-smi unavailable)"
    echo ""
fi

# Check/create venv
if [ ! -d "$VENV_DIR" ]; then
    echo "📦 Creating virtual environment..."
    python3.12 -m venv "$VENV_DIR"
fi

# Activate venv
source "$VENV_DIR/bin/activate"

# Check if SAM2 is installed
if ! python -c "import sam2" 2>/dev/null; then
    echo "📦 Installing SAM 2..."
    pip install --upgrade pip
    cd "$SAM2_DIR"
    pip install -e ".[notebooks]"
    pip install gradio
    echo "✓ Installation complete"
    echo ""
fi

# Check/download model checkpoints
if [ ! -f "$CHECKPOINTS_DIR/sam2.1_hiera_large.pt" ]; then
    echo "📥 Downloading SAM 2.1 checkpoints..."
    mkdir -p "$CHECKPOINTS_DIR"
    cd "$CHECKPOINTS_DIR"

    # Download the large model (best quality)
    wget -q --show-progress https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_large.pt

    echo "✓ Checkpoints downloaded"
    echo ""
fi

# Create output directory
mkdir -p "$OUTPUT_DIR"

echo "🌐 Starting SAM 2.1 Demo..."
echo "📡 Local:   http://localhost:8005"
echo "📡 LAN:     http://192.168.7.226:8005"
echo ""
echo "Features:"
echo "  - Click to segment objects in images"
echo "  - Track objects across video frames"
echo "  - Automatic mask generation"
echo "  - Box and point prompts"
echo ""
echo "Output saves to: $OUTPUT_DIR"
echo ""
echo "Press Ctrl+C to stop"
echo ""

export SAM2_OUTPUT_DIR="$OUTPUT_DIR"

# Memory optimization for 16GB VRAM
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

cd "$SAM2_DIR/demo"

# Check if there's a Gradio demo, otherwise create a simple one
if [ ! -f "gradio_app.py" ]; then
    cat > gradio_app.py << 'DEMO_EOF'
import gradio as gr
import torch
import numpy as np
import os
import datetime
from PIL import Image
from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor

# Configuration
OUTPUT_DIR = os.environ.get("SAM2_OUTPUT_DIR", os.path.expanduser("~/ai_generated/sam2"))
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Load model
checkpoint = "../checkpoints/sam2.1_hiera_large.pt"
model_cfg = "../sam2/configs/sam2.1/sam2.1_hiera_l.yaml"
predictor = SAM2ImagePredictor(build_sam2(model_cfg, checkpoint))

def segment_image(image, evt: gr.SelectData):
    if image is None:
        return None, None

    # Get click coordinates
    x, y = evt.index

    with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
        predictor.set_image(np.array(image))
        masks, scores, _ = predictor.predict(
            point_coords=np.array([[x, y]]),
            point_labels=np.array([1]),
            multimask_output=True,
        )

    # Get best mask
    best_mask = masks[np.argmax(scores)]

    # Create overlay
    overlay = np.array(image).copy()
    overlay[best_mask] = overlay[best_mask] * 0.5 + np.array([0, 255, 0]) * 0.5

    # Create mask image
    mask_img = (best_mask * 255).astype(np.uint8)

    # Save outputs
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    overlay_path = os.path.join(OUTPUT_DIR, f"sam2_overlay_{timestamp}.png")
    mask_path = os.path.join(OUTPUT_DIR, f"sam2_mask_{timestamp}.png")
    Image.fromarray(overlay.astype(np.uint8)).save(overlay_path)
    Image.fromarray(mask_img).save(mask_path)

    return Image.fromarray(overlay.astype(np.uint8)), Image.fromarray(mask_img)

with gr.Blocks(title="SAM 2.1 - Segment Anything") as demo:
    gr.Markdown("# 🎯 SAM 2.1 - Segment Anything")
    gr.Markdown("Click on an object in the image to segment it")

    with gr.Row():
        input_image = gr.Image(label="Input Image", type="pil")
        output_image = gr.Image(label="Segmented")
        mask_image = gr.Image(label="Mask")

    input_image.select(segment_image, [input_image], [output_image, mask_image])

demo.launch(server_name="0.0.0.0", server_port=8005)
DEMO_EOF
fi

python gradio_app.py
