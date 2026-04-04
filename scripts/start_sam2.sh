#!/bin/bash
# SAM 2.1 — Segment Anything Model 2 (Meta)
# Port: 8005
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="SAM 2.1"
PORT=8005
VENV="venv_sam2"
SAM2_DIR="$DRAGONSUITE_ROOT/projects/sam2"
DEMO_DIR="$SAM2_DIR/demo"
CHECKPOINTS_DIR="$SAM2_DIR/checkpoints"
OUTPUT_DIR="$HOME/ai_generated/sam2"

service_header "$SERVICE_NAME" "$PORT"
gpu_preflight "$PORT"
activate_venv "$VENV"
set_pytorch_env

# Check model checkpoint
if [ ! -f "$CHECKPOINTS_DIR/sam2.1_hiera_large.pt" ]; then
    echo "❌ SAM 2.1 checkpoint not found at: $CHECKPOINTS_DIR"
    echo "   Run: wget -P $CHECKPOINTS_DIR https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_large.pt"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"
export SAM2_OUTPUT_DIR="$OUTPUT_DIR"

# Create gradio_app.py if missing
if [ ! -f "$DEMO_DIR/gradio_app.py" ]; then
    mkdir -p "$DEMO_DIR"
    cat > "$DEMO_DIR/gradio_app.py" << 'DEMO_EOF'
import gradio as gr
import torch
import numpy as np
import os
import datetime
from PIL import Image
from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor

OUTPUT_DIR = os.environ.get("SAM2_OUTPUT_DIR", os.path.expanduser("~/ai_generated/sam2"))
os.makedirs(OUTPUT_DIR, exist_ok=True)

checkpoint = "../checkpoints/sam2.1_hiera_large.pt"
model_cfg = "../sam2/configs/sam2.1/sam2.1_hiera_l.yaml"
predictor = SAM2ImagePredictor(build_sam2(model_cfg, checkpoint))

def segment_image(image, evt: gr.SelectData):
    if image is None:
        return None, None
    x, y = evt.index
    with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
        predictor.set_image(np.array(image))
        masks, scores, _ = predictor.predict(
            point_coords=np.array([[x, y]]),
            point_labels=np.array([1]),
            multimask_output=True,
        )
    best_mask = masks[np.argmax(scores)]
    overlay = np.array(image).copy()
    overlay[best_mask] = overlay[best_mask] * 0.5 + np.array([0, 255, 0]) * 0.5
    mask_img = (best_mask * 255).astype(np.uint8)
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

echo "🚀 Starting $SERVICE_NAME..."
if pgrep -f "sam2/demo/gradio_app.py\|sam2.*gradio_app" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup bash -c "cd '$DEMO_DIR' && python gradio_app.py" > /tmp/sam2.log 2>&1 &
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 60; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Service did not start in time — check /tmp/sam2.log"
        tail -10 /tmp/sam2.log
        exit 1
    fi
fi
