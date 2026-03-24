#!/usr/bin/env python3
"""
LTX-2 (19B) — Text-to-video via diffusers LTX2Pipeline
Port 8016  |  Model: Lightricks/LTX-2

LTX2Pipeline is T2V only — no image conditioning parameter.
I2V would require a separate LTX2Image2VideoPipeline (not yet researched).
Verified call signature: prompt, negative_prompt, height, width, num_frames,
frame_rate, num_inference_steps, guidance_scale (default 4.0), generator,
decode_timestep, decode_noise_scale, output_type, return_dict.
"""

import os
import sys
import torch
import gradio as gr
from pathlib import Path
from datetime import datetime
from PIL import Image

os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

MODEL_DIR  = Path("/srv/containers/edq/models/ltxvideo_2")
OUTPUT_DIR = Path.home() / "ai_generated" / "ltxvideo2"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# --- Model check (fail fast) ---
if not MODEL_DIR.exists():
    print(f"❌ LTX-2 model not found: {MODEL_DIR}")
    print(f"   Run: bash scripts/download_ltxvideo2_models.sh")
    sys.exit(1)

# --- Load pipeline ---
print("⏳ Loading LTX-2 (19B)… this takes a minute")
from diffusers import LTX2Pipeline
from diffusers.utils import export_to_video

# LTX-2 is 19B parameters (~38GB at bf16). enable_model_cpu_offload() keeps
# only the active component on GPU, so peak VRAM is the largest single module
# rather than the full model. Falls within 16GB with VAE tiling.
pipe = LTX2Pipeline.from_pretrained(
    str(MODEL_DIR),
    torch_dtype=torch.bfloat16,
)
# No vae.enable_tiling() — LTX2 VAE tiler creates sub-padding-sized tiles at
# standard resolutions, causing RuntimeError in tiled_decode. Without tiling
# the VAE decodes fine within sequential cpu offload memory budget.
pipe.enable_sequential_cpu_offload()
print("✅ Model loaded")

NEG_PROMPT = "worst quality, inconsistent motion, blurry, jittery, distorted"

# Ember's Prehistoric Pursuit — Scene 1 (jungle arrival)
DEFAULT_PROMPT = (
    "Wide establishing shot of a dense misty jungle valley at dawn. "
    "Towering ferns, ancient trees, swirling fog. Sunlight filters through "
    "the canopy casting golden beams. A ginger-haired athletic woman in a "
    "turquoise tank top and khaki shorts emerges from the undergrowth, "
    "confident, carrying a crossbow. Cinematic, photorealistic."
)

DURATION_OPTIONS = {
    "2s  (49 frames)":   49,
    "5s (121 frames)":  121,
    "8s (193 frames)":  193,
    "10s (241 frames)": 241,
}

RESOLUTION_OPTIONS = {
    "768×512 (default)":     (768, 512),
    "512×768 (portrait)":    (512, 768),
    "704×480":               (704, 480),
    "1024×576 (widescreen)": (1024, 576),
}


def generate(prompt, neg_prompt, duration_label, resolution_label,
             num_steps, guidance, seed):
    num_frames = DURATION_OPTIONS[duration_label]
    width, height = RESOLUTION_OPTIONS[resolution_label]
    seed_val = int(seed) if seed >= 0 else torch.randint(0, 2**32, (1,)).item()
    generator = torch.Generator().manual_seed(seed_val)

    yield None, f"🎬 T2V · {num_frames} frames · {width}×{height} · seed {seed_val}…"

    try:
        output = pipe(
            prompt=prompt,
            negative_prompt=neg_prompt,
            num_frames=num_frames,
            height=height,
            width=width,
            frame_rate=24.0,
            num_inference_steps=num_steps,
            guidance_scale=guidance,
            generator=generator,
            output_type="pil",
            return_dict=True,
        )
        frames = output.frames[0]

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = OUTPUT_DIR / f"ltx2_{timestamp}_s{seed_val}.mp4"
        export_to_video(frames, str(out_path), fps=24)
        yield str(out_path), f"✅ Done — {out_path.name}  (seed: {seed_val})"

    except Exception as e:
        yield None, f"❌ Error: {e}"


# --- UI ---
CSS = """
body, .gradio-container { background: #1a1a2e !important; color: #e0e0e0 !important; }
.dark-header { background: #16213e; padding: 16px 20px; border-radius: 8px; margin-bottom: 12px; }
.dark-header h1 { color: #7c9cbf; margin: 0; font-size: 1.4em; }
.dark-header p  { color: #9ca3af; margin: 4px 0 0; font-size: 0.85em; }
label { color: #9ca3af !important; }
.gr-button-primary { background: #3b5998 !important; border: none !important; }
"""

with gr.Blocks(css=CSS, title="LTX-2") as demo:
    gr.HTML("""
    <div class="dark-header">
      <h1>🎬 LTX-2 (19B)</h1>
      <p>Text-to-video · Lightricks · port 8016</p>
    </div>
    """)

    with gr.Row():
        with gr.Column(scale=2):
            prompt = gr.Textbox(
                label="Prompt",
                value=DEFAULT_PROMPT,
                lines=4,
            )
            neg_prompt = gr.Textbox(
                label="Negative prompt",
                value=NEG_PROMPT,
                lines=2,
            )
            with gr.Row():
                duration = gr.Dropdown(
                    label="Duration",
                    choices=list(DURATION_OPTIONS.keys()),
                    value="5s (121 frames)",
                )
                resolution = gr.Dropdown(
                    label="Resolution",
                    choices=list(RESOLUTION_OPTIONS.keys()),
                    value="768×512 (default)",
                )
            with gr.Row():
                num_steps = gr.Slider(
                    label="Steps",
                    minimum=4, maximum=50, step=1, value=30,
                    info="20-30 recommended for LTX-2",
                )
                guidance = gr.Slider(
                    label="Guidance scale",
                    minimum=1.0, maximum=10.0, step=0.5, value=4.0,
                )
            seed = gr.Number(label="Seed (-1 = random)", value=-1, precision=0)
            btn = gr.Button("Generate", variant="primary")

        with gr.Column(scale=2):
            video_out = gr.Video(label="Output", height=360)
            status = gr.Textbox(label="Status", interactive=False)

    btn.click(
        generate,
        inputs=[prompt, neg_prompt, duration, resolution,
                num_steps, guidance, seed],
        outputs=[video_out, status],
    )

if __name__ == "__main__":
    demo.queue().launch(
        server_name="0.0.0.0",
        server_port=8016,
        show_api=False,
    )
