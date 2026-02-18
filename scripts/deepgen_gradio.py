#!/usr/bin/env python3
"""
DeepGen 1.0 - Gradio Interface
5B unified model (3B VLM + 2B DiT) for text-to-image generation and image editing.

Model: deepgenteam/DeepGen-1.0 (checkpoint: models/deepgen-1.0/model.pt)
Architecture: Qwen2.5-VL-3B + UniPic2-SD3.5M-Kontext-2B
Config: configs/models/deepgen_scb_blackwell.py (sdpa, Blackwell/sm_120 compatible)
"""

import sys
import os
import gradio as gr
import torch
import warnings
from pathlib import Path
from datetime import datetime

warnings.filterwarnings('ignore')

# DeepGen must run from its own project directory (config uses relative paths)
PROJECT_DIR = "/srv/containers/edq/projects/deepgen"
CHECKPOINT = "/srv/containers/edq/models/deepgen-1.0/model.pt"
CONFIG = "configs/models/deepgen_scb_blackwell.py"
OUTPUT_DIR = Path(os.path.expanduser("~/ai_generated/deepgen"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

os.chdir(PROJECT_DIR)
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

_model = None
_load_error = None


def check_prereqs():
    issues = []
    if not Path(CHECKPOINT).exists():
        issues.append(f"❌ Checkpoint not found: {CHECKPOINT}")
    if not Path(PROJECT_DIR, "model_zoo").exists():
        issues.append(
            "❌ model_zoo/ missing.\n"
            "   Run: bash scripts/download_deepgen_model_zoo.sh"
        )
    return issues


def load_model():
    global _model, _load_error
    if _model is not None:
        return True, "Model loaded"
    if _load_error:
        return False, _load_error

    issues = check_prereqs()
    if issues:
        _load_error = "\n".join(issues)
        return False, _load_error

    try:
        from xtuner.registry import BUILDER
        from mmengine.config import Config

        print(f"Loading config: {CONFIG}")
        config = Config.fromfile(CONFIG)

        print("Building model architecture from model_zoo...")
        model = BUILDER.build(config.model)

        print(f"Loading checkpoint: {CHECKPOINT}")
        state_dict = torch.load(CHECKPOINT, map_location='cpu')
        missing, unexpected = model.load_state_dict(state_dict, strict=False)
        if missing:
            print(f"  Missing keys: {len(missing)}")
        if unexpected:
            print(f"  Unexpected keys: {len(unexpected)}")

        print("Moving model to CUDA...")
        model = model.cuda()
        model.eval()

        _model = model
        print("✓ DeepGen model ready!")
        return True, "Model loaded"
    except Exception as e:
        import traceback
        _load_error = f"Error: {e}\n\n{traceback.format_exc()}"
        return False, _load_error


def generate_image(prompt, cfg_scale, num_steps, height, width, seed, progress=gr.Progress()):
    if not prompt or not prompt.strip():
        return None, "Please enter a prompt."

    progress(0.05, desc="Loading model...")
    ok, msg = load_model()
    if not ok:
        return None, f"Failed to load model:\n{msg}"

    try:
        generator = torch.Generator(device='cuda').manual_seed(int(seed))
        progress(0.2, desc="Generating image...")

        with torch.no_grad():
            images = _model.generate(
                prompt=[prompt.strip()],
                cfg_prompt=[""],
                pixel_values_src=None,
                cfg_scale=float(cfg_scale),
                num_steps=int(num_steps),
                generator=generator,
                height=int(height),
                width=int(width),
                progress_bar=False,
            )

        progress(0.9, desc="Saving...")
        from einops import rearrange
        from PIL import Image as PILImage

        images = rearrange(images, 'b c h w -> b h w c')
        images = torch.clamp(127.5 * images + 128.0, 0, 255).cpu().to(torch.uint8).numpy()

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = str(OUTPUT_DIR / f"deepgen_{ts}.png")
        PILImage.fromarray(images[0]).save(out_path)
        return out_path, f"✓ Saved: {out_path}"

    except Exception as e:
        import traceback
        return None, f"Error: {e}\n\n{traceback.format_exc()}"


def edit_image(src_image, prompt, cfg_scale, num_steps, height, width, seed, progress=gr.Progress()):
    from PIL import Image as PILImage

    if src_image is None:
        return None, "Please upload a source image."
    if not prompt or not prompt.strip():
        return None, "Please enter an editing prompt."

    progress(0.05, desc="Loading model...")
    ok, msg = load_model()
    if not ok:
        return None, f"Failed to load model:\n{msg}"

    try:
        if not isinstance(src_image, PILImage.Image):
            src_image = PILImage.fromarray(src_image).convert('RGB')
        else:
            src_image = src_image.convert('RGB')
        src_image = src_image.resize((int(width), int(height)))

        import torchvision.transforms as T
        pixel_values = T.ToTensor()(src_image).unsqueeze(0).cuda()

        generator = torch.Generator(device='cuda').manual_seed(int(seed))
        progress(0.2, desc="Editing image...")

        with torch.no_grad():
            images = _model.generate(
                prompt=[prompt.strip()],
                cfg_prompt=[""],
                pixel_values_src=[[pixel_values[0]]],
                cfg_scale=float(cfg_scale),
                num_steps=int(num_steps),
                generator=generator,
                height=int(height),
                width=int(width),
                progress_bar=False,
            )

        progress(0.9, desc="Saving...")
        from einops import rearrange
        from PIL import Image as PILImage

        images = rearrange(images, 'b c h w -> b h w c')
        images = torch.clamp(127.5 * images + 128.0, 0, 255).cpu().to(torch.uint8).numpy()

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = str(OUTPUT_DIR / f"deepgen_edit_{ts}.png")
        PILImage.fromarray(images[0]).save(out_path)
        return out_path, f"✓ Saved: {out_path}"

    except Exception as e:
        import traceback
        return None, f"Error: {e}\n\n{traceback.format_exc()}"


CUSTOM_CSS = """
body { background-color: #1e1e1e; }
.gradio-container { background-color: #1e1e1e !important; }
"""

with gr.Blocks(title="DeepGen 1.0") as demo:
    gr.Markdown(
        """
        # 🎨 DeepGen 1.0
        **5B unified multimodal model** — text-to-image generation and image editing.
        *3B VLM reasoning + 2B SD3.5 diffusion. First run loads model (~11GB VRAM, ~30s).*
        """
    )

    with gr.Tab("🖼️ Text-to-Image"):
        with gr.Row():
            with gr.Column(scale=1):
                t2i_prompt = gr.Textbox(
                    label="Prompt",
                    placeholder="A quiet bookstore with a sign that says 'READ'. A coffee cup on the table with the word 'MORNING'.",
                    lines=4,
                    value=""
                )
                with gr.Row():
                    t2i_width = gr.Slider(label="Width", minimum=256, maximum=1024, value=512, step=64)
                    t2i_height = gr.Slider(label="Height", minimum=256, maximum=1024, value=512, step=64)
                with gr.Row():
                    t2i_cfg = gr.Slider(label="CFG Scale", minimum=1.0, maximum=10.0, value=4.0, step=0.5)
                    t2i_steps = gr.Slider(label="Steps", minimum=10, maximum=100, value=50, step=5)
                t2i_seed = gr.Number(label="Seed", value=42, precision=0)
                t2i_btn = gr.Button("🎨 Generate", variant="primary", size="lg")
            with gr.Column(scale=1):
                t2i_output = gr.Image(label="Generated Image", type="filepath")
                t2i_status = gr.Textbox(label="Status", lines=3, interactive=False)

        t2i_btn.click(
            fn=generate_image,
            inputs=[t2i_prompt, t2i_cfg, t2i_steps, t2i_height, t2i_width, t2i_seed],
            outputs=[t2i_output, t2i_status],
            show_progress=True
        )

    with gr.Tab("✏️ Image Editing"):
        with gr.Row():
            with gr.Column(scale=1):
                edit_src = gr.Image(
                    label="Source Image",
                    type="pil",
                    sources=["upload", "clipboard"],
                    height=300
                )
                edit_prompt = gr.Textbox(
                    label="Edit Instruction",
                    placeholder="Make the sky purple and add stars.",
                    lines=3
                )
                with gr.Row():
                    edit_width = gr.Slider(label="Width", minimum=256, maximum=1024, value=512, step=64)
                    edit_height = gr.Slider(label="Height", minimum=256, maximum=1024, value=512, step=64)
                with gr.Row():
                    edit_cfg = gr.Slider(label="CFG Scale", minimum=1.0, maximum=10.0, value=4.0, step=0.5)
                    edit_steps = gr.Slider(label="Steps", minimum=10, maximum=100, value=50, step=5)
                edit_seed = gr.Number(label="Seed", value=42, precision=0)
                edit_btn = gr.Button("✏️ Edit Image", variant="primary", size="lg")
            with gr.Column(scale=1):
                edit_output = gr.Image(label="Edited Image", type="filepath")
                edit_status = gr.Textbox(label="Status", lines=3, interactive=False)

        edit_btn.click(
            fn=edit_image,
            inputs=[edit_src, edit_prompt, edit_cfg, edit_steps, edit_height, edit_width, edit_seed],
            outputs=[edit_output, edit_status],
            show_progress=True
        )


if __name__ == "__main__":
    print("=" * 50)
    print("DeepGen 1.0")
    print(f"Project dir: {PROJECT_DIR}")
    print(f"Checkpoint:  {CHECKPOINT}")
    print(f"Config:      {CONFIG}")
    print(f"Output dir:  {OUTPUT_DIR}")
    print("=" * 50)
    print("")

    issues = check_prereqs()
    if issues:
        print("⚠️  Setup incomplete:")
        for issue in issues:
            print(f"   {issue}")
        print("")
        print("Run: bash scripts/download_deepgen_model_zoo.sh")
        print("")
    else:
        print("✓ Prerequisites OK")
        print("NOTE: Model loads on first generate (~30s, ~11GB VRAM)")
        print("")

    demo.launch(
        server_name="0.0.0.0",
        server_port=8024,
        share=False,
        theme=gr.themes.Soft(),
        css=CUSTOM_CSS
    )
