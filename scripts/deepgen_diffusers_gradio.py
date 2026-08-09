#!/usr/bin/env python3
"""
DeepGen 1.0 diffusers dashboard app.

Uses the self-contained diffusers-format release so the Dashboard entry does not
depend on the older DeepGen repo, xtuner, or mmengine setup.
"""

import gc
import os
from datetime import datetime
from pathlib import Path

import gradio as gr
import torch
from PIL import Image


OUTPUT_DIR = Path(os.path.expanduser("~/ai_generated/deepgen"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MODELS_DIR = Path("/srv/containers/edq/models/deepgen-1.0-diffusers")
REQUIRED_MODEL_FILES = [
    MODELS_DIR / "model_index.json",
    MODELS_DIR / "deepgen_pipeline.py",
    MODELS_DIR / "connector" / "model.safetensors",
    MODELS_DIR / "transformer" / "diffusion_pytorch_model.safetensors",
    MODELS_DIR / "vae" / "diffusion_pytorch_model.safetensors",
    MODELS_DIR / "vlm" / "model.safetensors.index.json",
]

os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

LORA_DIR = Path("/srv/containers/edq/models/loras/deepgen")
LORA_DIR.mkdir(parents=True, exist_ok=True)

pipe = None
load_error = None
loaded_loras = []


def get_available_loras():
    lora_files = []
    for ext in ["*.safetensors", "*.bin", "*.pt"]:
        lora_files.extend(LORA_DIR.glob(ext))
        lora_files.extend(LORA_DIR.glob(f"**/{ext}"))
    loras = ["None"]
    for f in sorted(set(lora_files)):
        try:
            loras.append(str(f.relative_to(LORA_DIR)))
        except ValueError:
            loras.append(f.name)
    return loras


def apply_lora(lora_name, lora_scale=1.0):
    """Load a LoRA onto the DeepGen transformer directly via PEFT.

    DeepGenPipeline doesn't inherit SD3LoraLoaderMixin (no pipe.load_lora_weights),
    but the transformer it wraps already mixes in diffusers' PeftAdapterMixin, so
    LoRA adapters are loaded straight onto pipe.transformer instead.
    """
    global loaded_loras
    if pipe is None:
        return "Load model first"
    if loaded_loras:
        try:
            pipe.transformer.unload_lora()
        except Exception:
            pass
        loaded_loras = []
    if lora_name == "None" or not lora_name:
        return "No LoRA loaded"
    lora_path = LORA_DIR / lora_name
    if not lora_path.exists():
        return f"LoRA not found: {lora_path}"
    try:
        from safetensors.torch import load_file
        state_dict = load_file(str(lora_path))
        pipe.transformer.load_lora_adapter(state_dict, prefix=None, adapter_name="default")
        pipe.transformer.set_adapters(["default"], [lora_scale])
        loaded_loras = [lora_name]
        return f"LoRA loaded: {lora_name}"
    except Exception as e:
        return f"Error loading LoRA: {e}"


def refresh_loras():
    return gr.update(choices=get_available_loras())


def clear_memory():
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def check_models():
    missing = [path for path in REQUIRED_MODEL_FILES if not path.exists() or path.stat().st_size == 0]
    incomplete = list(MODELS_DIR.glob("**/.cache/huggingface/download/*.incomplete"))
    if not missing and not incomplete:
        return None

    lines = [
        "Complete DeepGen models are not present.",
        "Run: bash scripts/download_deepgen_models.sh",
    ]
    if missing:
        lines.append("")
        lines.append("Missing files:")
        lines.extend(f"  {path}" for path in missing)
    if incomplete:
        lines.append("")
        lines.append("Incomplete Hugging Face download shards are still present.")
    return "\n".join(lines)


def load_pipeline():
    global pipe, load_error
    if pipe is not None:
        return True, "Model loaded"
    if load_error:
        return False, load_error

    issue = check_models()
    if issue:
        load_error = issue
        return False, issue

    try:
        from diffusers import DiffusionPipeline

        print("Loading DeepGen 1.0 diffusers pipeline from local models...")
        pipe = DiffusionPipeline.from_pretrained(
            str(MODELS_DIR),
            torch_dtype=torch.bfloat16,
            trust_remote_code=True,
            local_files_only=True,
        )
        if torch.cuda.is_available():
            pipe.enable_model_cpu_offload()
        print("DeepGen pipeline loaded.")
        return True, "Model loaded"
    except Exception as exc:
        import traceback

        load_error = f"{exc}\n\n{traceback.format_exc()}"
        clear_memory()
        return False, load_error


def save_image(image, prefix):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = OUTPUT_DIR / f"{prefix}_{timestamp}.png"
    image.save(output_path)
    return str(output_path)


def generate_image(prompt, negative_prompt, width, height, steps, guidance_scale, seed, lora_name, lora_scale, progress=gr.Progress()):
    if not prompt or not prompt.strip():
        return None, "Enter a prompt."

    progress(0.05, desc="Loading model...")
    ok, message = load_pipeline()
    if not ok:
        return None, f"Failed to load model:\n{message}"

    lora_status = apply_lora(lora_name, lora_scale)

    try:
        progress(0.15, desc="Generating...")
        result = pipe(
            prompt=prompt.strip(),
            negative_prompt=(negative_prompt or "").strip(),
            width=int(width),
            height=int(height),
            num_inference_steps=int(steps),
            guidance_scale=float(guidance_scale),
            seed=int(seed),
        )
        image = result.images[0]
        output_path = save_image(image, "deepgen")
        clear_memory()
        status = f"Saved: {output_path}"
        if loaded_loras:
            status += f"\n{lora_status} (scale: {lora_scale})"
        return output_path, status
    except Exception as exc:
        import traceback

        clear_memory()
        return None, f"Error:\n{exc}\n\n{traceback.format_exc()}"


def edit_image(source_image, prompt, negative_prompt, width, height, steps, guidance_scale, seed, lora_name, lora_scale, progress=gr.Progress()):
    if source_image is None:
        return None, "Upload a source image."
    if not prompt or not prompt.strip():
        return None, "Enter an editing prompt."

    progress(0.05, desc="Loading model...")
    ok, message = load_pipeline()
    if not ok:
        return None, f"Failed to load model:\n{message}"

    lora_status = apply_lora(lora_name, lora_scale)

    try:
        if not isinstance(source_image, Image.Image):
            source_image = Image.fromarray(source_image)
        source_image = source_image.convert("RGB")

        progress(0.15, desc="Editing...")
        result = pipe(
            prompt=prompt.strip(),
            image=source_image,
            negative_prompt=(negative_prompt or "").strip(),
            width=int(width),
            height=int(height),
            num_inference_steps=int(steps),
            guidance_scale=float(guidance_scale),
            seed=int(seed),
        )
        image = result.images[0]
        output_path = save_image(image, "deepgen_edit")
        clear_memory()
        status = f"Saved: {output_path}"
        if loaded_loras:
            status += f"\n{lora_status} (scale: {lora_scale})"
        return output_path, status
    except Exception as exc:
        import traceback

        clear_memory()
        return None, f"Error:\n{exc}\n\n{traceback.format_exc()}"


with gr.Blocks(title="DeepGen 1.0") as demo:
    with gr.Tab("Text To Image"):
        with gr.Row():
            with gr.Column():
                t2i_prompt = gr.Textbox(
                    label="Prompt",
                    lines=4,
                    value="A small brass sign on a workbench that clearly says DRAGON, warm studio lighting.",
                )
                t2i_negative = gr.Textbox(label="Negative Prompt", value="", lines=2)
                with gr.Row():
                    t2i_width = gr.Slider(label="Width", minimum=256, maximum=1024, value=512, step=64)
                    t2i_height = gr.Slider(label="Height", minimum=256, maximum=1024, value=512, step=64)
                with gr.Row():
                    t2i_steps = gr.Slider(label="Steps", minimum=10, maximum=60, value=30, step=5)
                    t2i_guidance = gr.Slider(label="Guidance", minimum=1.0, maximum=10.0, value=4.0, step=0.5)
                t2i_seed = gr.Number(label="Seed", value=42, precision=0)
                with gr.Accordion("LoRA Settings", open=False):
                    with gr.Row():
                        t2i_lora = gr.Dropdown(choices=get_available_loras(), value="None", label="LoRA", scale=3)
                        t2i_lora_refresh = gr.Button("Refresh", scale=1, size="sm")
                    t2i_lora_scale = gr.Slider(0.0, 2.0, value=0.8, step=0.05, label="LoRA Scale")
                    gr.Markdown(f"Place LoRA files in: `{LORA_DIR}`")
                t2i_button = gr.Button("Generate", variant="primary")
            with gr.Column():
                t2i_output = gr.Image(label="Output", type="filepath")
                t2i_status = gr.Textbox(label="Status", lines=4)

        t2i_button.click(
            fn=generate_image,
            inputs=[t2i_prompt, t2i_negative, t2i_width, t2i_height, t2i_steps, t2i_guidance, t2i_seed, t2i_lora, t2i_lora_scale],
            outputs=[t2i_output, t2i_status],
            show_progress=True,
        )
        t2i_lora_refresh.click(fn=refresh_loras, outputs=[t2i_lora])

    with gr.Tab("Image Editing"):
        with gr.Row():
            with gr.Column():
                edit_source = gr.Image(label="Source Image", type="pil", sources=["upload", "clipboard"])
                edit_prompt = gr.Textbox(label="Prompt", lines=4)
                edit_negative = gr.Textbox(label="Negative Prompt", value="", lines=2)
                with gr.Row():
                    edit_width = gr.Slider(label="Width", minimum=256, maximum=1024, value=512, step=64)
                    edit_height = gr.Slider(label="Height", minimum=256, maximum=1024, value=512, step=64)
                with gr.Row():
                    edit_steps = gr.Slider(label="Steps", minimum=10, maximum=60, value=30, step=5)
                    edit_guidance = gr.Slider(label="Guidance", minimum=1.0, maximum=10.0, value=4.0, step=0.5)
                edit_seed = gr.Number(label="Seed", value=42, precision=0)
                with gr.Accordion("LoRA Settings", open=False):
                    with gr.Row():
                        edit_lora = gr.Dropdown(choices=get_available_loras(), value="None", label="LoRA", scale=3)
                        edit_lora_refresh = gr.Button("Refresh", scale=1, size="sm")
                    edit_lora_scale = gr.Slider(0.0, 2.0, value=0.8, step=0.05, label="LoRA Scale")
                    gr.Markdown(f"Place LoRA files in: `{LORA_DIR}`")
                edit_button = gr.Button("Edit", variant="primary")
            with gr.Column():
                edit_output = gr.Image(label="Output", type="filepath")
                edit_status = gr.Textbox(label="Status", lines=4)

        edit_button.click(
            fn=edit_image,
            inputs=[edit_source, edit_prompt, edit_negative, edit_width, edit_height, edit_steps, edit_guidance, edit_seed, edit_lora, edit_lora_scale],
            outputs=[edit_output, edit_status],
            show_progress=True,
        )
        edit_lora_refresh.click(fn=refresh_loras, outputs=[edit_lora])


if __name__ == "__main__":
    print("DeepGen 1.0 diffusers")
    print(f"Models: {MODELS_DIR}")
    print(f"Output: {OUTPUT_DIR}")
    issue = check_models()
    if issue:
        print(issue)
    demo.launch(
        server_name="0.0.0.0",
        server_port=8024,
        share=False,
        allowed_paths=[str(OUTPUT_DIR)],
        show_error=True,
    )
