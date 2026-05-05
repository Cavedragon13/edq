#!/usr/bin/env python3
"""Z-Anime — Anime fine-tune of Z-Image Base (SeeSee21/Z-Anime)
6B S3-DiT, AIO FP8 variants, natural language prompts, Apache 2.0"""

import gradio as gr
import torch
from pathlib import Path
from datetime import datetime
import gc

MODEL_DIR  = Path("/srv/containers/edq/models/zanime/aio")
OUTPUT_DIR = Path.home() / "ai_generated" / "zanime"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
PORT = 8008

# AIO variant files — each bundles model + VAE + text encoder
AIO_FILES = {
    "Base FP8 (~6GB)":         "z-anime-base-aio-fp8.safetensors",
    "Distill 8-Step FP8":      "z-anime-distill-8step-aio-fp8.safetensors",
    "Distill 4-Step FP8":      "z-anime-distill-4step-aio-fp8.safetensors",
    "Base BF16 (~12GB)":       "z-anime-base-aio-bf16.safetensors",
    "Distill 8-Step BF16":     "z-anime-distill-8step-aio-bf16.safetensors",
    "Distill 4-Step BF16":     "z-anime-distill-4step-aio-bf16.safetensors",
}

# Per-variant recommended settings from model card
VARIANT_DEFAULTS = {
    "Base FP8 (~6GB)":         {"steps": 40, "cfg": 4.0, "cfg_lock": False},
    "Distill 8-Step FP8":      {"steps": 8,  "cfg": 1.0, "cfg_lock": True},
    "Distill 4-Step FP8":      {"steps": 4,  "cfg": 1.0, "cfg_lock": True},
    "Base BF16 (~12GB)":       {"steps": 40, "cfg": 4.0, "cfg_lock": False},
    "Distill 8-Step BF16":     {"steps": 8,  "cfg": 1.0, "cfg_lock": True},
    "Distill 4-Step BF16":     {"steps": 4,  "cfg": 1.0, "cfg_lock": True},
}

RESOLUTIONS = {
    "Portrait / Character (832×1216)":  (832, 1216),
    "Landscape / Scene (1216×832)":     (1216, 832),
    "Square / General (1024×1024)":     (1024, 1024),
    "Tall / Wallpaper (768×1344)":      (768, 1344),
    "Cinematic (1920×1088)":            (1920, 1088),
    "Small / Fast (512×512)":           (512, 512),
}

_pipe = None
_loaded_variant = None


def available_variants():
    return [k for k, v in AIO_FILES.items() if (MODEL_DIR / v).exists()] or ["No models — run download_zanime_models.sh"]


def evict():
    global _pipe, _loaded_variant
    if _pipe is not None:
        try:
            _pipe.remove_all_hooks()
        except Exception:
            pass
        del _pipe
        _pipe = None
        _loaded_variant = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


def load_variant(variant: str):
    global _pipe, _loaded_variant
    if _loaded_variant == variant and _pipe is not None:
        return
    evict()
    from diffusers import ZImagePipeline
    path = str(MODEL_DIR / AIO_FILES[variant])
    dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
    print(f"Loading {variant} from {path} ...")
    _pipe = ZImagePipeline.from_single_file(path, torch_dtype=dtype)
    _pipe.enable_sequential_cpu_offload()
    _pipe.enable_attention_slicing()
    _loaded_variant = variant
    print(f"Ready: {variant}")


def generate(prompt, negative, variant, resolution, steps, cfg, seed):
    if "No models" in variant:
        return None, "❌ Run: bash scripts/download_zanime_models.sh"
    w, h = RESOLUTIONS[resolution]
    try:
        load_variant(variant)
    except Exception as e:
        return None, f"❌ Load failed: {e}"
    generator = torch.Generator(device="cpu").manual_seed(int(seed))
    try:
        result = _pipe(
            prompt=prompt,
            negative_prompt=negative or "",
            width=w, height=h,
            num_inference_steps=int(steps),
            guidance_scale=float(cfg),
            generator=generator,
        )
        img = result.images[0]
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = variant.split()[0].lower()
        path = OUTPUT_DIR / f"zanime_{slug}_{ts}.png"
        img.save(path)
        return str(path), f"✅ Saved: {path.name}"
    except Exception as e:
        return None, f"❌ Generation failed: {e}"


def update_defaults(variant):
    d = VARIANT_DEFAULTS.get(variant, {"steps": 40, "cfg": 4.0, "cfg_lock": False})
    cfg_visible = not d["cfg_lock"]
    return gr.update(value=d["steps"]), gr.update(value=d["cfg"], visible=cfg_visible)


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
            variant_dd = gr.Dropdown(choices=available_variants(), value=available_variants()[0], label="Model variant")
            prompt     = gr.Textbox(label="Prompt", lines=3, placeholder="A young woman in a kimono, cherry blossoms, soft lighting...")
            negative   = gr.Textbox(label="Negative prompt", lines=2, value="blurry, bad anatomy, watermark, text")
            resolution = gr.Dropdown(choices=list(RESOLUTIONS.keys()), value="Portrait / Character (832×1216)", label="Resolution")
            with gr.Row():
                steps = gr.Slider(1, 60, value=40, step=1, label="Steps")
                cfg   = gr.Slider(1.0, 9.0, value=4.0, step=0.5, label="CFG scale")
            seed   = gr.Number(value=42, label="Seed", precision=0)
            run_btn = gr.Button("Generate", variant="primary")

        with gr.Column(scale=1):
            output_img = gr.Image(label="Output", type="filepath")
            status     = gr.Textbox(label="Status", interactive=False)

    variant_dd.change(update_defaults, inputs=variant_dd, outputs=[steps, cfg])
    run_btn.click(generate, inputs=[prompt, negative, variant_dd, resolution, steps, cfg, seed],
                  outputs=[output_img, status])

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=PORT, share=False)
