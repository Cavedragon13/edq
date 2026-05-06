#!/usr/bin/env python3
"""Z-Anime — Anime fine-tune of Z-Image Base (SeeSee21/Z-Anime)
6B S3-DiT, diffusers layout, sequential CPU offload, Apache 2.0

Loads from the local diffusers subfolder (same pattern as Z-Image Base).
AIO files in models/zanime/aio/ are ComfyUI format and not used here."""

import gradio as gr
import torch
from pathlib import Path
from datetime import datetime
import gc

DIFFUSERS_DIR = Path("/srv/containers/edq/models/zanime/diffusers")
OUTPUT_DIR    = Path.home() / "ai_generated" / "zanime"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
PORT = 8008

RESOLUTIONS = {
    "Portrait / Character (832×1216)":  (832, 1216),
    "Landscape / Scene (1216×832)":     (1216, 832),
    "Square / General (1024×1024)":     (1024, 1024),
    "Tall / Wallpaper (768×1344)":      (768, 1344),
    "Cinematic (1920×1088)":            (1920, 1088),
    "Small / Fast (512×512)":           (512, 512),
}

_pipe = None


def evict():
    global _pipe
    if _pipe is not None:
        try:
            _pipe.remove_all_hooks()
        except Exception:
            pass
        del _pipe
        _pipe = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


def get_pipe():
    global _pipe
    if _pipe is not None:
        return _pipe
    from diffusers import ZImagePipeline
    dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
    print(f"Loading Z-Anime from {DIFFUSERS_DIR} ...")
    _pipe = ZImagePipeline.from_pretrained(
        str(DIFFUSERS_DIR),
        local_files_only=True,
        torch_dtype=dtype,
    )
    _pipe.enable_sequential_cpu_offload()
    _pipe.enable_attention_slicing()
    print("Z-Anime ready.")
    return _pipe


def generate(prompt, negative, resolution, steps, cfg, seed):
    w, h = RESOLUTIONS[resolution]
    try:
        pipe = get_pipe()
    except Exception as e:
        return None, f"❌ Load failed: {e}"
    generator = torch.Generator(device="cpu").manual_seed(int(seed))
    try:
        result = pipe(
            prompt=prompt,
            negative_prompt=negative or "",
            width=w, height=h,
            num_inference_steps=int(steps),
            guidance_scale=float(cfg),
            generator=generator,
        )
        img = result.images[0]
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = OUTPUT_DIR / f"zanime_{ts}.png"
        img.save(out_path)
        return str(out_path), f"✅ Saved: {out_path.name}"
    except Exception as e:
        return None, f"❌ Generation failed: {e}"


DARK_CSS = """
.gradio-container { background: #0f0f14 !important; color: #e0e0e0 !important; }
.block, .panel, .form { background: #1a1a2e !important; border-color: #2d2d4e !important; }
label, .label-wrap, span { color: #c4b5fd !important; }
input, textarea, select, .input-container { background: #1e1e2e !important; color: #e0e0e0 !important; border-color: #4a5568 !important; }
button.primary { background: #7c3aed !important; border-color: #6d28d9 !important; }
button.secondary { background: #2d2d4e !important; color: #c4b5fd !important; }
"""

with gr.Blocks(theme=gr.themes.Base(), css=DARK_CSS, title="Z-Anime") as demo:
    gr.Markdown("# 🎌 Z-Anime\nAnime fine-tune of Z-Image Base · 6B S3-DiT · Natural language prompts")
    with gr.Row():
        with gr.Column(scale=1):
            prompt     = gr.Textbox(label="Prompt", lines=3,
                                    placeholder="A young woman in a kimono, cherry blossoms, soft lighting...")
            negative   = gr.Textbox(label="Negative prompt", lines=2,
                                    value="blurry, bad anatomy, watermark, text")
            resolution = gr.Dropdown(choices=list(RESOLUTIONS.keys()),
                                     value="Portrait / Character (832×1216)", label="Resolution")
            with gr.Row():
                steps = gr.Slider(1, 60, value=40, step=1, label="Steps")
                cfg   = gr.Slider(1.0, 9.0, value=4.0, step=0.5, label="CFG scale")
            seed    = gr.Number(value=42, label="Seed", precision=0)
            run_btn = gr.Button("Generate", variant="primary")
        with gr.Column(scale=1):
            output_img = gr.Image(label="Output", type="filepath")
            status     = gr.Textbox(label="Status", interactive=False)

    run_btn.click(generate,
                  inputs=[prompt, negative, resolution, steps, cfg, seed],
                  outputs=[output_img, status])

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=PORT, share=False)
