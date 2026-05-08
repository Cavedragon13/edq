#!/usr/bin/env python3
"""Z-Anime — Anime fine-tune of Z-Image Base (SeeSee21/Z-Anime).

This dashboard app intentionally uses the repository's Diffusers layout.
For the remote Hugging Face repo that would be:
    ZImagePipeline.from_pretrained("SeeSee21/Z-Anime", subfolder="diffusers")

The local downloader stores only that subfolder under models/zanime/diffusers,
so the runtime loads that directory directly.

The AIO safetensors are ComfyUI checkpoints. Loading an AIO file through this
Diffusers app, or describing this app as a 4-step/8-step AIO launcher, produces
confusing behavior and bad expectations. Keep those paths separate.
"""

import gradio as gr
import torch
from pathlib import Path
from datetime import datetime
import gc

MODEL_ROOT    = Path("/srv/containers/edq/models/zanime")
DIFFUSERS_DIR = MODEL_ROOT / "diffusers"
OUTPUT_DIR    = Path.home() / "ai_generated" / "zanime"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
PORT = 8008
MODEL_MODE = "Diffusers Base BF16"
MODEL_NOTE = "Uses SeeSee21/Z-Anime/diffusers. AIO files are ComfyUI-only."

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
    # Text encoder is saved with mixed BF16+FP8 weights; cast to uniform BF16
    # before sequential CPU offload installs its hooks (which lock dtypes).
    _pipe.text_encoder = _pipe.text_encoder.to(dtype)
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
        return str(out_path), f"✅ Saved: {out_path.name}\n{MODEL_MODE} · {w}×{h} · {steps} steps · CFG {cfg}"
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

with gr.Blocks(title="Z-Anime") as demo:
    gr.Markdown(
        "# Z-Anime\n"
        "Anime fine-tune of Z-Image Base · Diffusers Base BF16 · Natural language prompts"
    )
    with gr.Row():
        with gr.Column(scale=1):
            prompt     = gr.Textbox(label="Prompt", lines=3,
                                    value=("A young anime girl with long silver hair and golden eyes, wearing a "
                                           "traditional shrine maiden outfit with white haori and red hakama. "
                                           "She stands in a sunlit bamboo forest, cherry blossoms falling softly "
                                           "around her. Warm afternoon light filtering through the trees, detailed "
                                           "fabric shading, expressive face, calm serene expression, high quality "
                                           "anime illustration with fine line work."),
                                    placeholder="Use a full natural-language scene description, not short tag lists.")
            negative   = gr.Textbox(label="Negative prompt", lines=2,
                                    value=("blurry, low quality, worst quality, bad anatomy, malformed hands, "
                                           "extra fingers, missing fingers, text, watermark, logo, jpeg artifacts, "
                                           "photorealistic, 3d render"))
            resolution = gr.Dropdown(choices=list(RESOLUTIONS.keys()),
                                     value="Portrait / Character (832×1216)", label="Resolution")
            with gr.Row():
                steps = gr.Slider(1, 60, value=40, step=1, label="Steps")
                cfg   = gr.Slider(1.0, 9.0, value=4.0, step=0.5, label="CFG scale")
            seed    = gr.Number(value=42, label="Seed", precision=0)
            run_btn = gr.Button("Generate", variant="primary")
            gr.Markdown(f"`{MODEL_MODE}`\n\n{MODEL_NOTE}")
        with gr.Column(scale=1):
            output_img = gr.Image(label="Output", type="filepath")
            status     = gr.Textbox(label="Status", interactive=False)

    run_btn.click(generate,
                  inputs=[prompt, negative, resolution, steps, cfg, seed],
                  outputs=[output_img, status])

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=PORT, share=False,
                allowed_paths=[str(OUTPUT_DIR)],
                theme=gr.themes.Base(), css=DARK_CSS)
