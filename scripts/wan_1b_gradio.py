#!/usr/bin/env python3
"""
Wan2.1-T2V-1.3B — Standalone text-to-video interface
Port 8016  |  Model: Wan-AI/Wan2.1-T2V-1.3B-Diffusers
"""

import os
import sys
import torch
import gradio as gr
from pathlib import Path
from datetime import datetime

os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

MODEL_DIR = Path("/srv/containers/edq/models/wan_1b")
OUTPUT_DIR = Path.home() / "ai_generated" / "wan_1b"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# --- Model check (fail fast) ---
REQUIRED = ["transformer", "vae", "tokenizer", "scheduler"]
for sub in REQUIRED:
    if not (MODEL_DIR / sub).exists():
        print(f"❌ Model not found: {MODEL_DIR / sub}")
        print(f"   Run: bash scripts/download_wan_1b_models.sh")
        sys.exit(1)

# --- Load pipeline ---
print("⏳ Loading Wan2.1-T2V-1.3B...")
from diffusers import WanPipeline, AutoModel
from diffusers.schedulers.scheduling_unipc_multistep import UniPCMultistepScheduler
from diffusers.utils import export_to_video

vae = AutoModel.from_pretrained(str(MODEL_DIR), subfolder="vae", torch_dtype=torch.float32)
pipe = WanPipeline.from_pretrained(str(MODEL_DIR), vae=vae, torch_dtype=torch.bfloat16)
pipe.scheduler = UniPCMultistepScheduler.from_config(pipe.scheduler.config, flow_shift=5.0)
pipe.enable_model_cpu_offload()
print("✅ Model loaded")

NEG_PROMPT = (
    "Bright tones, overexposed, static, blurred details, subtitles, style, works, paintings, "
    "images, static, overall gray, worst quality, low quality, JPEG compression residue, ugly, "
    "incomplete, extra fingers, poorly drawn hands, poorly drawn faces, deformed, disfigured, "
    "misshapen limbs, fused fingers, still picture, messy background, three legs, "
    "many people in the background, walking backwards"
)

DEFAULT_PROMPT = (
    "The camera slowly pushes in on a woman reading at a sunlit café table. "
    "Warm afternoon light, shallow depth of field, dust motes drifting in the air. "
    "Photorealistic, cinematic, 4K."
)

DURATION_OPTIONS = {
    "2s (33 frames)": 33,
    "3s (49 frames)": 49,
    "5s (81 frames)": 81,
    "8s (129 frames)": 129,
}


def generate(prompt, neg_prompt, duration_label, steps, guidance, seed):
    num_frames = DURATION_OPTIONS[duration_label]
    seed_val = int(seed) if seed >= 0 else torch.randint(0, 2**32, (1,)).item()
    generator = torch.Generator().manual_seed(seed_val)

    yield None, f"🎬 Generating ({num_frames} frames, {steps} steps, seed {seed_val})…"

    try:
        frames = pipe(
            prompt=prompt,
            negative_prompt=neg_prompt,
            num_frames=num_frames,
            guidance_scale=guidance,
            num_inference_steps=steps,
            generator=generator,
        ).frames[0]

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = OUTPUT_DIR / f"wan1b_{timestamp}_s{seed_val}.mp4"
        export_to_video(frames, str(out_path), fps=16)
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

with gr.Blocks(css=CSS, title="Wan 1.3B — T2V") as demo:
    gr.HTML("""
    <div class="dark-header">
      <h1>🎬 Wan2.1-T2V-1.3B</h1>
      <p>Fast text-to-video · 832×480 · ~8GB VRAM · Apache 2.0</p>
    </div>
    """)

    with gr.Row():
        with gr.Column(scale=2):
            prompt = gr.Textbox(
                label="Prompt",
                value=DEFAULT_PROMPT,
                lines=4,
                placeholder="Describe the video…",
            )
            neg_prompt = gr.Textbox(
                label="Negative prompt",
                value=NEG_PROMPT,
                lines=3,
            )
            with gr.Row():
                duration = gr.Dropdown(
                    label="Duration",
                    choices=list(DURATION_OPTIONS.keys()),
                    value="5s (81 frames)",
                )
                steps = gr.Slider(label="Steps", minimum=10, maximum=50, value=20, step=1)
            with gr.Row():
                guidance = gr.Slider(label="Guidance scale", minimum=1.0, maximum=10.0, value=5.0, step=0.5)
                seed = gr.Number(label="Seed (-1 = random)", value=-1, precision=0)
            btn = gr.Button("Generate", variant="primary")

        with gr.Column(scale=2):
            video_out = gr.Video(label="Output", height=360)
            status = gr.Textbox(label="Status", interactive=False)

    btn.click(
        generate,
        inputs=[prompt, neg_prompt, duration, steps, guidance, seed],
        outputs=[video_out, status],
    )

if __name__ == "__main__":
    demo.queue().launch(
        server_name="0.0.0.0",
        server_port=8016,
        favicon_path="/srv/containers/edq/media/favicons/wan1b.svg",
    )
