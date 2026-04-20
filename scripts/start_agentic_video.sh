#!/bin/bash
# Agentic Video Editor - 4-Agent Video Ad Pipeline (Gradio Wrapper)
# Director → Trim Refiner → Editor → Reviewer agents
# Port 8044, LAN accessible
set -euo pipefail

cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="Agentic Video Editor"
PORT=8044
VENV="venv_agentic_video"
VENV_DIR="$DRAGONSUITE_ROOT/$VENV"
OUTPUT_DIR="$HOME/ai_generated/agentic_video"
LOG_FILE="/tmp/agentic_video.log"

service_header "$SERVICE_NAME" "$PORT"

echo "🔧 Pre-flight checks..."
vram_status
clear_port "$PORT"
echo "✓ VRAM status:"
vram_status
echo ""

if [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo "❌ Virtual environment not found: $VENV_DIR"
    exit 1
fi

activate_venv "$VENV"

mkdir -p "$OUTPUT_DIR"

# Load .env for GOOGLE_API_KEY
if [ -f "$DRAGONSUITE_ROOT/.env" ]; then
    set -a
    source "$DRAGONSUITE_ROOT/.env"
    set +a
fi

# Verify GOOGLE_API_KEY is set
if [ -z "${GOOGLE_API_KEY:-}" ]; then
    echo "❌ GOOGLE_API_KEY not found in .env — required for Gemini API calls"
    exit 1
fi

export GOOGLE_API_KEY
export HF_HUB_DISABLE_TELEMETRY=1
export PORT

echo "🚀 Starting $SERVICE_NAME (Gradio wrapper)..."

# Create a minimal Gradio wrapper that calls ave edit
python << "GRADIO_WRAPPER"
import gradio as gr
import subprocess
import os
import json
from pathlib import Path
import tempfile
from datetime import datetime

OUTPUT_BASE = os.path.expanduser("~/ai_generated/agentic_video")
Path(OUTPUT_BASE).mkdir(parents=True, exist_ok=True)

def process_video(video_file, creative_brief, pipeline_yaml=""):
    """Wrapper for ave edit command"""
    if not video_file:
        return None, "❌ Please upload a video file"

    if not creative_brief.strip():
        return None, "❌ Please provide a creative brief"

    try:
        # Use the uploaded file as-is (Gradio handles temp file management)
        footage_dir = tempfile.mkdtemp(prefix="agentic_")
        Path(footage_dir).joinpath(Path(video_file).name).write_bytes(Path(video_file).read_bytes())

        output_dir = Path(OUTPUT_BASE) / datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir.mkdir(parents=True, exist_ok=True)

        # Build ave command
        cmd = ["ave", "edit",
               "--footage-dir", footage_dir,
               "--brief", json.dumps({"brief": creative_brief}),
               "--output", str(output_dir)]

        # Run ave edit
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)

        if result.returncode != 0:
            return None, f"❌ Pipeline failed:\n{result.stderr}"

        # Find output video
        output_video = list(output_dir.glob("*.mp4"))
        if not output_video:
            return None, f"❌ No output video found in {output_dir}"

        return str(output_video[0]), f"✅ Video processed successfully\nOutput: {output_video[0].name}"

    except subprocess.TimeoutExpired:
        return None, "❌ Processing timeout (>1 hour)"
    except Exception as e:
        return None, f"❌ Error: {str(e)}"

# Gradio interface
with gr.Blocks(title="Agentic Video Editor", theme=gr.themes.Soft()) as iface:
    gr.Markdown("# 🎬 Agentic Video Editor")
    gr.Markdown("Upload a video + creative brief → 4-agent pipeline produces edited ad")

    with gr.Row():
        with gr.Column():
            video_input = gr.File(label="📹 Footage", file_types=["video"])
            brief_input = gr.Textbox(
                label="📝 Creative Brief",
                placeholder="E.g., 'Create a 30-second product demo with upbeat energy'",
                lines=3
            )
            pipeline_input = gr.Textbox(
                label="🔧 Pipeline YAML (optional)",
                placeholder="Leave empty for default",
                lines=2
            )
            submit_btn = gr.Button("🚀 Process Video", variant="primary")

        with gr.Column():
            video_output = gr.Video(label="✅ Output Video")
            status_output = gr.Textbox(label="Status", interactive=False)

    submit_btn.click(
        process_video,
        inputs=[video_input, brief_input, pipeline_input],
        outputs=[video_output, status_output]
    )

    gr.Markdown(f"**Output folder:** `{OUTPUT_BASE}`")

port = int(os.environ.get('PORT', 8044))
iface.launch(server_name="0.0.0.0", server_port=port, share=False)
GRADIO_WRAPPER

echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
echo "   Output folder: $OUTPUT_DIR"
