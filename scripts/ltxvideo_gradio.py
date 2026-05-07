#!/usr/bin/env python3
"""
LTX-Video-0.9.8-distilled — Standalone text-to-video / image-to-video interface
Port 8028  |  Model: Lightricks/LTX-Video-0.9.8-distilled
"""

import os
import sys
import torch
import gradio as gr
from pathlib import Path
from datetime import datetime
from PIL import Image

os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

MODEL_DIR     = Path("/srv/containers/edq/models/ltxvideo_098")
UPSCALER_DIR  = Path("/srv/containers/edq/models/ltxvideo_upscaler_098")
OUTPUT_DIR    = Path.home() / "ai_generated" / "ltxvideo"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# --- Model check (fail fast) ---
for p, label in [(MODEL_DIR, "ltxvideo"), (UPSCALER_DIR, "ltxvideo_upscaler")]:
    if not p.exists():
        print(f"❌ Model not found: {p}")
        print(f"   Run: bash scripts/download_ltxvideo_models.sh")
        sys.exit(1)

# --- Load pipelines ---
print("⏳ Loading LTX-Video-0.9.8-distilled…")
from diffusers import LTXConditionPipeline, LTXLatentUpsamplePipeline
from diffusers.pipelines.ltx.pipeline_ltx_condition import LTXVideoCondition
from diffusers.utils import export_to_video, load_image

pipe = LTXConditionPipeline.from_pretrained(str(MODEL_DIR), torch_dtype=torch.bfloat16)
pipe_up = LTXLatentUpsamplePipeline.from_pretrained(
    str(UPSCALER_DIR), vae=pipe.vae, torch_dtype=torch.bfloat16
)
# 13B model: enable_model_cpu_offload() OOMs on 16GB (loads whole transformer ~13GB)
# sequential offload loads one layer at a time — fits, but slower (~16s/step)
pipe.enable_sequential_cpu_offload()
pipe_up.enable_sequential_cpu_offload()
pipe.vae.enable_tiling()
print("✅ Model loaded")

NEG_PROMPT  = "worst quality, inconsistent motion, blurry, jittery, distorted"
DEFAULT_PROMPT = (
    "A lone astronaut walks across a vast rust-red desert under a twin-sun sky. "
    "Cinematic wide shot, long shadows, dust swirling around boots. "
    "Photorealistic, 4K, atmospheric."
)

DURATION_OPTIONS = {
    "2s  (57 frames)":  57,
    "5s (121 frames)": 121,
    "7s (161 frames)": 161,
    "11s (257 frames)": 257,
}


def _round_vae(h, w):
    r = pipe.vae_spatial_compression_ratio
    return h - (h % r), w - (w % r)


def generate(prompt, neg_prompt, image_input, duration_label, quality_mode, seed):
    num_frames = DURATION_OPTIONS[duration_label]
    seed_val = int(seed) if seed >= 0 else torch.randint(0, 2**32, (1,)).item()
    generator = torch.Generator().manual_seed(seed_val)

    # I2V: prepare condition from image
    conditions = None
    if image_input is not None:
        img = Image.fromarray(image_input) if not isinstance(image_input, Image.Image) else image_input
        from diffusers.utils import export_to_video as _etv
        import tempfile, imageio
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp_path = tmp.name
        imageio.mimsave(tmp_path, [img], fps=1)
        vid = load_image(img)  # single frame treated as video start
        condition_video = [img]
        conditions = [LTXVideoCondition(video=condition_video, frame_index=0)]
        num_frames = min(num_frames, 96)  # I2V cap

    mode_label = "quality (3-pass)" if quality_mode else "fast (1-pass)"
    yield None, f"🎬 Generating {num_frames} frames · {mode_label} · seed {seed_val}…"

    # Resolutions
    exp_h, exp_w = 512, 704
    scale = 2 / 3
    lo_h, lo_w = _round_vae(int(exp_h * scale), int(exp_w * scale))

    try:
        # Pass 1: generate at reduced resolution
        latents = pipe(
            conditions=conditions,
            prompt=prompt,
            negative_prompt=neg_prompt,
            width=lo_w, height=lo_h,
            num_frames=num_frames,
            num_inference_steps=7,
            guidance_scale=1.0,
            decode_timestep=0.05,
            decode_noise_scale=0.025,
            generator=generator,
            output_type="latent",
        ).frames

        if quality_mode:
            yield None, "🔼 Upscaling…"
            # Pass 2: spatial upscale
            up_latents = pipe_up(latents=latents, output_type="latent").frames
            hi_h, hi_w = _round_vae(lo_h * 2, lo_w * 2)

            yield None, "✨ Refining…"
            # Pass 3: denoise at full resolution
            frames = pipe(
                conditions=conditions,
                prompt=prompt,
                negative_prompt=neg_prompt,
                width=hi_w, height=hi_h,
                num_frames=num_frames,
                denoise_strength=0.3,
                num_inference_steps=10,
                latents=up_latents,
                guidance_scale=1.0,
                decode_timestep=0.05,
                decode_noise_scale=0.025,
                image_cond_noise_scale=0.025,
                generator=generator,
                output_type="pil",
            ).frames[0]
            frames = [f.resize((exp_w, exp_h)) for f in frames]
        else:
            # Fast: decode the low-res latents directly
            frames = pipe(
                conditions=conditions,
                prompt=prompt,
                negative_prompt=neg_prompt,
                width=exp_w, height=exp_h,
                num_frames=num_frames,
                latents=latents,
                denoise_strength=0.0,
                num_inference_steps=1,
                guidance_scale=1.0,
                decode_timestep=0.05,
                decode_noise_scale=0.025,
                output_type="pil",
            ).frames[0]

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = OUTPUT_DIR / f"ltxv_{timestamp}_s{seed_val}.mp4"
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

with gr.Blocks(css=CSS, title="LTX-Video 0.9.8") as demo:
    gr.HTML("""
    <div class="dark-header">
      <h1>🎬 LTX-Video 0.9.8 Distilled</h1>
      <p>Text-to-video & image-to-video · 7 steps · 704×512 · Lightricks</p>
    </div>
    """)

    with gr.Row():
        with gr.Column(scale=2):
            prompt = gr.Textbox(
                label="Prompt (English only)",
                value=DEFAULT_PROMPT,
                lines=4,
            )
            neg_prompt = gr.Textbox(
                label="Negative prompt",
                value=NEG_PROMPT,
                lines=2,
            )
            image_input = gr.Image(
                label="Start frame (optional — enables image-to-video)",
                type="numpy",
                height=160,
            )
            with gr.Row():
                duration = gr.Dropdown(
                    label="Duration",
                    choices=list(DURATION_OPTIONS.keys()),
                    value="5s (121 frames)",
                )
                quality = gr.Checkbox(
                    label="Quality mode (3-pass upscale)",
                    value=True,
                )
            with gr.Row():
                seed = gr.Number(label="Seed (-1 = random)", value=-1, precision=0)
            btn = gr.Button("Generate", variant="primary")

        with gr.Column(scale=2):
            video_out = gr.Video(label="Output", height=360)
            status = gr.Textbox(label="Status", interactive=False)

    btn.click(
        generate,
        inputs=[prompt, neg_prompt, image_input, duration, quality, seed],
        outputs=[video_out, status],
    )

if __name__ == "__main__":
    demo.queue().launch(
        server_name="0.0.0.0",
        server_port=8028,
        favicon_path="/srv/containers/edq/media/favicons/ltxvideo.svg",
    )
