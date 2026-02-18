#!/usr/bin/env python3
"""
LTX-2 Dedicated Interface
Simplified video generation with LTX-2 19B model
Port 8016
"""

import os
import sys
import json
import gradio as gr
from pathlib import Path

# Add Wan2GP to path
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
WAN2GP_DIR = PROJECT_DIR / "projects" / "Wan2GP"
sys.path.insert(0, str(WAN2GP_DIR))

# Set output directory
OUTPUT_DIR = Path.home() / "ai_generated" / "ltx2"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Load LTX-2 configuration
CONFIG_PATH = WAN2GP_DIR / "defaults" / "ltx2_19B.json"
with open(CONFIG_PATH) as f:
    LTX2_CONFIG = json.load(f)

DEFAULT_PROMPT = """A warm sunny backyard. The camera starts in a tight cinematic close-up of a woman and a man in their 30s, facing each other with serious expressions. The woman, emotional and dramatic, says softly, "That's it... Dad's lost it. And we've lost Dad." The man exhales, slightly annoyed: "Stop being so dramatic, Jess." A beat. He glances aside, then mutters defensively, "He's just having fun." The camera slowly pans right, revealing the grandfather in the garden wearing enormous butterfly wings, waving his arms in the air like he's trying to take off. He shouts, "Wheeeew!" as he flaps his wings with full commitment. The woman covers her face, on the verge of tears. The tone is deadpan, absurd, and quietly tragic."""


def generate_video(prompt, start_image, end_image, video_length, steps, guidance_scale, seed):
    """Generate video using LTX-2."""
    try:
        # Import WanGP2 modules
        from wgp import generate_video_from_settings

        # Build settings
        settings = {
            "prompt": prompt,
            "model_mode": "ltx2_19B",
            "video_length": video_length,
            "num_inference_steps": steps,
            "guidance_scale": guidance_scale,
            "seed": seed if seed >= 0 else -1,
            "image_start": start_image,
            "image_end": end_image,
            "resolution": "832x480",  # LTX-2 default
            "output_filename": "",
        }

        # Generate
        status = "🎬 Generating video with LTX-2 19B..."
        print(status)

        result = generate_video_from_settings(settings)

        if result and "output" in result:
            output_path = result["output"]
            return output_path, f"✅ Video generated successfully!\n\nOutput: {Path(output_path).name}"
        else:
            return None, "❌ Generation failed - no output returned"

    except Exception as e:
        import traceback
        error_msg = f"❌ Error: {str(e)}\n\n{traceback.format_exc()}"
        print(error_msg)
        return None, error_msg


def create_ui():
    """Create LTX-2 Gradio interface."""

    # Dark theme by default
    theme = gr.themes.Soft(primary_hue="blue").set(
        body_background_fill="*neutral_950",
        body_background_fill_dark="*neutral_950",
        button_primary_background_fill="*primary_600",
        button_primary_background_fill_hover="*primary_700",
    )

    with gr.Blocks(title="LTX-2 Video Generator", theme=theme) as app:
        gr.Markdown("""
        # 🎬 LTX-2 Video Generator

        **Model:** LTX-2 Dev 19B (20 second video generation with audio soundtrack)

        LTX-2 generates video up to 20s with an audio soundtrack. Supports start/end keyframes
        and sliding-window continuation. You can force the audio soundtrack by providing an Audio Prompt.

        **Features:**
        - Text-to-video generation
        - Optional start/end keyframes
        - Audio soundtrack generation
        - Use tags `<S>` and `<E>` to delimit speaker words
        - Prefix with "Audio:" to set background noise
        """)

        with gr.Row():
            with gr.Column(scale=2):
                gr.Markdown("### Prompt")
                prompt_input = gr.Textbox(
                    label="Video Description",
                    placeholder="Describe the scene, dialogue, and audio...",
                    value=DEFAULT_PROMPT,
                    lines=10
                )

                gr.Markdown("### Optional Keyframes")
                with gr.Row():
                    start_image = gr.Image(
                        label="Start Frame (optional)",
                        type="filepath",
                        height=200
                    )
                    end_image = gr.Image(
                        label="End Frame (optional)",
                        type="filepath",
                        height=200
                    )

                gr.Markdown("### Generation Settings")
                with gr.Row():
                    video_length = gr.Slider(
                        minimum=33,
                        maximum=241,
                        value=121,
                        step=16,
                        label="Video Length (frames)",
                        info="33=~1s, 121=~5s, 241=~10s"
                    )
                    steps = gr.Slider(
                        minimum=20,
                        maximum=60,
                        value=40,
                        step=1,
                        label="Inference Steps",
                        info="More steps = better quality, slower"
                    )

                with gr.Row():
                    guidance_scale = gr.Slider(
                        minimum=1.0,
                        maximum=10.0,
                        value=4.0,
                        step=0.5,
                        label="Guidance Scale",
                        info="How closely to follow prompt"
                    )
                    seed = gr.Number(
                        label="Seed",
                        value=-1,
                        precision=0,
                        info="-1 for random"
                    )

                generate_btn = gr.Button("🚀 Generate Video", variant="primary", size="lg")

            with gr.Column(scale=1):
                gr.Markdown("### Output")
                video_output = gr.Video(
                    label="Generated Video",
                    show_download_button=True
                )
                status_output = gr.Markdown()

        generate_btn.click(
            fn=generate_video,
            inputs=[
                prompt_input,
                start_image,
                end_image,
                video_length,
                steps,
                guidance_scale,
                seed
            ],
            outputs=[video_output, status_output]
        )

        gr.Markdown(f"""
        ---
        **Output Directory:** `{OUTPUT_DIR}`

        **Tips:**
        - Use dialogue tags: `<S>spoken words<E>`
        - Add audio description: "Audio: background music, sound effects"
        - Keyframes help guide the generation
        - Longer videos require more VRAM

        **Model Info:** LTX-2 generates 24fps video with synchronized audio soundtrack.
        """)

    return app


if __name__ == "__main__":
    import torch

    print("🎬 LTX-2 Video Generator")
    print("=" * 50)
    print()

    # Check GPU
    if torch.cuda.is_available():
        print(f"🎮 GPU: {torch.cuda.get_device_name(0)}")
        total_mem = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"💾 VRAM: {total_mem:.1f} GB")
    else:
        print("⚠️  No GPU detected - this will be very slow!")

    print()
    print(f"📁 Output directory: {OUTPUT_DIR}")
    print()
    print("🌐 Starting server...")
    print("📡 Local:   http://localhost:8016")
    print("📡 LAN:     http://192.168.7.226:8016")
    print()

    app = create_ui()
    app.launch(
        server_name="0.0.0.0",
        server_port=8016,
        share=False
    )
