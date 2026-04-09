#!/usr/bin/env python3
"""
JustDubit Gradio Interface
Video dubbing with joint audio-visual diffusion
"""

import gradio as gr
import subprocess
import os
from pathlib import Path
import sys

# Add project to path
PROJECT_DIR = Path("/srv/containers/edq/projects/just-dub-it")
sys.path.insert(0, str(PROJECT_DIR))

OUTPUT_DIR = Path("/home/edq/ai_generated/justdubit")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def run_dubbing(
    input_video,
    prompt_text,
    height,
    width,
    progress=gr.Progress()
):
    """Run JustDubit video dubbing"""

    if not input_video:
        return None, "❌ Please upload a video file"

    if not prompt_text.strip():
        return None, "❌ Please provide a dubbing prompt"

    try:
        progress(0.1, desc="Setting up...")

        # Generate output path
        output_path = OUTPUT_DIR / f"dubbed_{Path(input_video).stem}.mp4"

        # Build command (using uv to run in just-dub-it venv)
        cmd = [
            "/home/edq/.local/bin/uv", "run",
            "python", "src/ltx_pipelines/pipeline_justdubit.py",
            "--checkpoint_path", "${CHECKPOINT}",  # TODO: Set checkpoint paths
            "--gemma_root", "${GEMMA_ROOT}",
            "--video_conditioning", input_video, "1.0",
            "--prompt", prompt_text,
            "--height", str(height),
            "--width", str(width),
            "--output_path", str(output_path)
        ]

        progress(0.3, desc="Running dubbing pipeline...")

        # Note: This is a placeholder - actual model paths need to be configured
        return None, """⚠️ JustDubit requires model checkpoints to be downloaded first.

**Required Models:**
1. LTX-2 AV Checkpoint (ltx-2-19b-dev.safetensors)
2. JustDubit LoRA (ltx-2-19b-ic-lora-lipdubbing.safetensors)
3. Distilled LoRA (ltx-2-19b-distilled-lora-384.safetensors)
4. Spatial Upscaler (ltx-2-spatial-upscaler-x2-1.0.safetensors)
5. Gemma Text Encoder (gemma-3-12b-it-qat-q4_0-unquantized)

Download from: https://huggingface.co/justdubit/justdubit

Then update paths in this script."""

    except Exception as e:
        return None, f"❌ Error: {str(e)}"

# Create Gradio interface
with gr.Blocks(title="JustDubit - Video Dubbing") as demo:
    gr.Markdown("# 🎬 JustDubit - Video Dubbing")
    gr.Markdown("Multilingual video dubbing with synchronized lip-sync using joint audio-visual diffusion")

    with gr.Row():
        with gr.Column():
            input_video = gr.Video(label="Input Video", sources=["upload"])
            prompt_text = gr.Textbox(
                label="Dubbing Prompt",
                placeholder="The person is speaking English, saying: 'Hello, world!'",
                lines=3
            )

            with gr.Row():
                height = gr.Slider(256, 1024, value=512, step=64, label="Height (will be 2x upsampled)")
                width = gr.Slider(256, 1024, value=768, step=64, label="Width (will be 2x upsampled)")

            run_btn = gr.Button("🎬 Generate Dubbed Video", variant="primary")

        with gr.Column():
            output_video = gr.Video(label="Dubbed Video")
            status_text = gr.Textbox(label="Status", lines=10)

    gr.Markdown("""
    ### Notes:
    - Output resolution is 2x the input size (e.g., 512x768 → 1024x1536)
    - Requires ~50GB of model checkpoints
    - Processing time depends on video length and resolution
    """)

    run_btn.click(
        fn=run_dubbing,
        inputs=[input_video, prompt_text, height, width],
        outputs=[output_video, status_text]
    )

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=8022,
        share=False,
        favicon_path="/srv/containers/edq/media/favicons/justdubit.svg"
    )
