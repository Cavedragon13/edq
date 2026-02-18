#!/usr/bin/env python3
"""
DragonFlux Klein - FLUX.2-klein Gradio Interface
Fast text-to-image and image-to-image generation with LoRA support
Optimized for RTX 5070 Ti (16GB VRAM) with CPU offloading
"""

import gradio as gr
import torch
from pathlib import Path
import os
from datetime import datetime
from PIL import Image

# Configuration
MODELS = {
    "4b": {
        "id": "black-forest-labs/FLUX.2-klein-4B",
        "name": "FLUX.2-klein-4B (Recommended)",
        "vram": "~12GB",
        "recommended_steps": 4,
        "recommended_guidance": 1.0,
    },
    "9b": {
        "id": "black-forest-labs/FLUX.2-klein-9B",
        "name": "FLUX.2-klein-9B",
        "vram": "~29GB (needs CPU offload)",
        "recommended_steps": 4,
        "recommended_guidance": 1.0,
    },
    "flux1-dev": {
        "id": "/srv/containers/edq/models/creative_upscale/flux_dev",
        "name": "FLUX.1-dev (HD Quality)",
        "vram": "~24GB (heavy CPU offload)",
        "recommended_steps": 28,
        "recommended_guidance": 3.5,
    },
}

FLUX1_DEV_PATH = "/srv/containers/edq/models/creative_upscale/flux_dev"

# Aspect ratio presets (width x height, multiples of 64)
ASPECT_RATIOS = {
    "1:1 (Square)": (1024, 1024),
    "9:16 (Portrait)": (576, 1024),
    "16:9 (Landscape)": (1024, 576),
    "4:5 (Portrait)": (768, 960),
    "5:4 (Landscape)": (960, 768),
    "Custom": None,  # User controls sliders
}

OUTPUT_DIR = Path(os.path.expanduser("~/ai_generated/flux2-klein"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# LoRA directory - will be created if doesn't exist
LORA_DIR = Path(os.path.expanduser("~/models/loras/flux-klein"))
LORA_DIR.mkdir(parents=True, exist_ok=True)

# Global pipeline state
pipe = None
current_model = None
loaded_loras = []
device = "cuda" if torch.cuda.is_available() else "cpu"
dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32

# Dragon favicon as base64 SVG
DRAGON_FAVICON = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <defs>
    <linearGradient id="dragonGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#8B5CF6"/>
      <stop offset="100%" style="stop-color:#EC4899"/>
    </linearGradient>
  </defs>
  <circle cx="32" cy="32" r="30" fill="url(#dragonGrad)"/>
  <path d="M20 42 Q25 35 32 38 Q39 35 44 42 L42 38 Q38 32 32 35 Q26 32 22 38 Z" fill="#fff" opacity="0.9"/>
  <circle cx="24" cy="28" r="4" fill="#fff"/>
  <circle cx="40" cy="28" r="4" fill="#fff"/>
  <circle cx="25" cy="28" r="2" fill="#1a1a2e"/>
  <circle cx="41" cy="28" r="2" fill="#1a1a2e"/>
  <path d="M15 18 Q20 12 25 16" stroke="#fff" stroke-width="2" fill="none"/>
  <path d="M49 18 Q44 12 39 16" stroke="#fff" stroke-width="2" fill="none"/>
  <path d="M28 44 L32 48 L36 44" stroke="#fff" stroke-width="2" fill="none" stroke-linecap="round"/>
</svg>
"""


def get_available_loras():
    """Scan LoRA directory for available LoRA files"""
    lora_files = []
    if LORA_DIR.exists():
        for ext in ["*.safetensors", "*.bin", "*.pt"]:
            lora_files.extend(LORA_DIR.glob(ext))
        # Also check subdirectories (common for HuggingFace downloads)
        for ext in ["*.safetensors", "*.bin", "*.pt"]:
            lora_files.extend(LORA_DIR.glob(f"**/{ext}"))

    # Return relative paths for cleaner display
    loras = ["None"]
    for f in sorted(set(lora_files)):
        try:
            rel_path = f.relative_to(LORA_DIR)
            loras.append(str(rel_path))
        except ValueError:
            loras.append(f.name)

    return loras


def load_pipeline(model_variant="4b"):
    """Lazy load the FLUX.2-klein pipeline with aggressive memory optimizations"""
    global pipe, current_model, loaded_loras

    if pipe is not None and current_model == model_variant:
        return pipe

    # Clear old model if switching
    if pipe is not None:
        del pipe
        torch.cuda.empty_cache()
        import gc
        gc.collect()
        pipe = None
        loaded_loras = []

    model_info = MODELS.get(model_variant, MODELS["4b"])
    model_id = model_info["id"]

    print(f"Loading {model_info['name']}...")
    try:
        # Set memory optimization environment (expandable_segments is superior to max_split_size_mb)
        os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

        if model_variant == "flux1-dev":
            from diffusers import FluxPipeline
            if not os.path.isdir(model_id):
                raise FileNotFoundError(
                    f"FLUX.1-dev not found at {model_id}\n"
                    "Run: bash scripts/download_creative_upscale_models.sh"
                )
            pipe = FluxPipeline.from_pretrained(model_id, torch_dtype=dtype, local_files_only=True)
        else:
            from diffusers import Flux2KleinPipeline
            pipe = Flux2KleinPipeline.from_pretrained(model_id, torch_dtype=dtype)

        # Use sequential CPU offload for maximum memory savings
        pipe.enable_sequential_cpu_offload()

        # Enable VAE optimizations
        if hasattr(pipe, 'vae'):
            pipe.vae.enable_slicing()
            pipe.vae.enable_tiling()

        current_model = model_variant
        print(f"Model loaded with CPU offloading + VAE optimizations")
    except Exception as e:
        print(f"Failed to load model: {e}")
        raise
    return pipe


def apply_lora(lora_name, lora_scale=1.0):
    """Load and apply a LoRA to the current pipeline"""
    global pipe, loaded_loras

    if pipe is None:
        return "Load a model first"

    if lora_name == "None" or not lora_name:
        # Unload any existing LoRAs
        if loaded_loras:
            try:
                pipe.unload_lora_weights()
                loaded_loras = []
                return "LoRA unloaded"
            except Exception as e:
                return f"Error unloading LoRA: {e}"
        return "No LoRA loaded"

    lora_path = LORA_DIR / lora_name
    if not lora_path.exists():
        return f"LoRA not found: {lora_path}"

    try:
        # Unload previous LoRAs first
        if loaded_loras:
            pipe.unload_lora_weights()

        # Load the new LoRA
        pipe.load_lora_weights(str(lora_path))
        loaded_loras = [lora_name]
        return f"LoRA loaded: {lora_name} (scale: {lora_scale})"
    except Exception as e:
        return f"Error loading LoRA: {e}"


def generate_image(
    prompt: str,
    model_variant: str,
    aspect_ratio: str,
    width: int,
    height: int,
    guidance_scale: float,
    num_inference_steps: int,
    seed: int,
    lora_name: str,
    lora_scale: float,
    input_image: Image.Image = None,
    img2img_strength: float = 0.75,
    progress=gr.Progress()
):
    """Generate an image from text prompt or transform an input image"""
    if not prompt or prompt.strip() == "":
        return None, "Please enter a prompt"

    # Map display name back to key
    if "FLUX.1-dev" in model_variant or "HD Quality" in model_variant:
        variant_key = "flux1-dev"
    elif "4B" in model_variant:
        variant_key = "4b"
    else:
        variant_key = "9b"

    progress(0, desc="Loading model...")
    try:
        pipeline = load_pipeline(variant_key)
    except Exception as e:
        return None, f"Failed to load model: {str(e)}"

    # Apply LoRA if selected
    if lora_name and lora_name != "None":
        progress(0.1, desc="Loading LoRA...")
        lora_status = apply_lora(lora_name, lora_scale)
        print(lora_status)

    # Get dimensions from aspect ratio or use custom
    if aspect_ratio != "Custom" and aspect_ratio in ASPECT_RATIOS:
        width, height = ASPECT_RATIOS[aspect_ratio]

    # Handle seed
    if seed == -1:
        seed = torch.randint(0, 2**32, (1,)).item()
    generator = torch.Generator(device="cpu").manual_seed(int(seed))

    progress(0.2, desc="Generating image...")
    try:
        # Prepare generation kwargs
        gen_kwargs = {
            "prompt": prompt,
            "height": height,
            "width": width,
            "guidance_scale": guidance_scale,
            "num_inference_steps": num_inference_steps,
            "generator": generator,
        }

        # Add LoRA scale if using a LoRA
        if loaded_loras and lora_scale != 1.0:
            gen_kwargs["cross_attention_kwargs"] = {"scale": lora_scale}

        # Image-to-image mode (FLUX.2-klein uses image as starting point, no strength param)
        if input_image is not None:
            # Resize input image to target dimensions
            input_image = input_image.convert("RGB")
            input_image = input_image.resize((width, height), Image.Resampling.LANCZOS)
            gen_kwargs["image"] = input_image
            # More steps = more transformation from original
            # Scale steps based on strength slider (4-20 steps)
            scaled_steps = int(4 + (num_inference_steps - 4) * img2img_strength)
            gen_kwargs["num_inference_steps"] = max(4, scaled_steps)
            mode = "img2img"
        else:
            mode = "txt2img"

        result = pipeline(**gen_kwargs)
        image = result.images[0]

        # Save image
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_prompt = "".join(c for c in prompt[:50] if c.isalnum() or c in " -_").strip()
        safe_prompt = safe_prompt.replace(" ", "_")
        lora_suffix = f"_lora-{Path(lora_name).stem}" if lora_name and lora_name != "None" else ""
        filename = f"{timestamp}_{safe_prompt}{lora_suffix}.png"
        filepath = OUTPUT_DIR / filename
        image.save(filepath)

        lora_info = f"\nLoRA: {lora_name} (scale: {lora_scale})" if loaded_loras else ""
        progress(1.0, desc="Done!")
        return image, f"Generated ({mode}) | {width}x{height}\nSaved: {filepath}\nSeed: {seed}{lora_info}"

    except torch.cuda.OutOfMemoryError:
        return None, "Out of GPU memory. Try a smaller resolution or 1:1 aspect ratio."
    except Exception as e:
        error_msg = str(e)
        return None, f"Generation failed: {error_msg}"


def refresh_loras():
    """Refresh the LoRA dropdown"""
    return gr.update(choices=get_available_loras())


def on_model_change(model_variant):
    """Auto-adjust recommended settings when model changes."""
    if "FLUX.1-dev" in model_variant or "HD Quality" in model_variant:
        steps = MODELS["flux1-dev"]["recommended_steps"]
        guidance = MODELS["flux1-dev"]["recommended_guidance"]
        warning = "> ⚠️ **HD Mode**: Slower generation (~60s/image). Requires FLUX.1-dev downloaded."
        return steps, guidance, gr.update(value=warning, visible=True)
    elif "4B" in model_variant:
        steps = MODELS["4b"]["recommended_steps"]
        guidance = MODELS["4b"]["recommended_guidance"]
    else:
        steps = MODELS["9b"]["recommended_steps"]
        guidance = MODELS["9b"]["recommended_guidance"]
    return steps, guidance, gr.update(value="", visible=False)


def update_dimensions(aspect_ratio):
    """Update width/height sliders based on aspect ratio selection"""
    if aspect_ratio == "Custom":
        return gr.update(interactive=True), gr.update(interactive=True)
    elif aspect_ratio in ASPECT_RATIOS and ASPECT_RATIOS[aspect_ratio]:
        w, h = ASPECT_RATIOS[aspect_ratio]
        return gr.update(value=w, interactive=False), gr.update(value=h, interactive=False)
    return gr.update(interactive=True), gr.update(interactive=True)


# Custom CSS for dragon theme
custom_css = """
.gradio-container {
    max-width: 1400px !important;
}
.dragon-header {
    text-align: center;
    background: linear-gradient(135deg, #8B5CF6 0%, #EC4899 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    font-size: 2.5em;
    font-weight: bold;
    margin-bottom: 0.5em;
}
.dragon-subtitle {
    text-align: center;
    color: #9ca3af;
    margin-bottom: 1em;
}
footer {
    visibility: hidden;
}
"""

# Build Gradio interface
with gr.Blocks(
    title="DragonFlux Klein"
) as app:

    gr.HTML('<div class="dragon-header">DragonFlux Klein</div>')
    gr.HTML('<div class="dragon-subtitle">FLUX.2-klein Image Generator with LoRA Support</div>')

    with gr.Row():
        with gr.Column(scale=1):
            # Model selection
            model_selector = gr.Dropdown(
                choices=[
                    f"{MODELS['4b']['name']} - {MODELS['4b']['vram']}",
                    f"{MODELS['9b']['name']} - {MODELS['9b']['vram']}",
                    f"{MODELS['flux1-dev']['name']} - {MODELS['flux1-dev']['vram']}",
                ],
                value=f"{MODELS['4b']['name']} - {MODELS['4b']['vram']}",
                label="Model",
                info="4B recommended for 16GB VRAM. FLUX.1-dev = HD quality but slower (~60s/image)"
            )
            model_warning = gr.Markdown(visible=False, value="")

            # Prompt
            prompt_input = gr.Textbox(
                label="Prompt",
                placeholder="A majestic dragon soaring through storm clouds, scales shimmering with violet lightning...",
                lines=3
            )

            # Aspect ratio and dimensions
            with gr.Row():
                aspect_ratio = gr.Dropdown(
                    choices=list(ASPECT_RATIOS.keys()),
                    value="1:1 (Square)",
                    label="Aspect Ratio"
                )

            with gr.Row():
                width_input = gr.Slider(
                    minimum=256, maximum=1536, value=1024, step=64,
                    label="Width", interactive=False
                )
                height_input = gr.Slider(
                    minimum=256, maximum=1536, value=1024, step=64,
                    label="Height", interactive=False
                )

            # LoRA section
            with gr.Accordion("LoRA Settings", open=False):
                with gr.Row():
                    lora_dropdown = gr.Dropdown(
                        choices=get_available_loras(),
                        value="None",
                        label="LoRA",
                        scale=3
                    )
                    refresh_btn = gr.Button("Refresh", scale=1, size="sm")

                lora_scale = gr.Slider(
                    minimum=0.0, maximum=2.0, value=1.0, step=0.05,
                    label="LoRA Scale",
                    info="Strength of LoRA effect (1.0 = full)"
                )

                gr.Markdown(f"Place LoRA files (.safetensors) in: `{LORA_DIR}`")

            # Image-to-image section
            with gr.Accordion("Image-to-Image", open=False):
                input_image = gr.Image(
                    label="Input Image (optional)",
                    type="pil",
                    sources=["upload", "clipboard"]
                )
                img2img_strength = gr.Slider(
                    minimum=0.1, maximum=1.0, value=0.5, step=0.05,
                    label="Transformation Amount",
                    info="Higher = more deviation from original (scales inference steps)"
                )
                gr.Markdown("*FLUX.2-klein uses image as starting point. Transformation controlled by step count.*")

            # Advanced settings
            with gr.Accordion("Advanced Settings", open=False):
                guidance_scale = gr.Slider(
                    minimum=0.0, maximum=5.0, value=1.0, step=0.1,
                    label="Guidance Scale",
                    info="1.0 recommended for this model"
                )
                num_steps = gr.Slider(
                    minimum=1, maximum=20, value=4, step=1,
                    label="Inference Steps",
                    info="4 steps is optimal"
                )
                seed_input = gr.Number(
                    value=-1,
                    label="Seed",
                    info="-1 for random"
                )

            generate_btn = gr.Button("Generate", variant="primary", size="lg")

        with gr.Column(scale=1):
            output_image = gr.Image(label="Generated Image", type="pil")
            status_output = gr.Textbox(label="Status", lines=3, interactive=False)

    # Example prompts
    gr.Examples(
        examples=[
            ["A majestic dragon perched on a crystal mountain peak, scales reflecting aurora borealis"],
            ["Portrait of an elegant elven queen with silver hair and glowing amethyst eyes"],
            ["A cyberpunk street market at night with neon signs and rain-slicked streets"],
            ["Enchanted forest clearing with bioluminescent mushrooms and floating fireflies"],
            ["A steampunk airship sailing through golden sunset clouds"],
        ],
        inputs=prompt_input,
        label="Example Prompts"
    )

    gr.Markdown(f"""
    ---
    **Tips:** 4B model recommended for 16GB VRAM | 4 steps optimal | Images saved to `{OUTPUT_DIR}`

    **LoRAs:** Place `.safetensors` files in `{LORA_DIR}` and click Refresh
    """)

    # Event handlers
    model_selector.change(
        fn=on_model_change,
        inputs=[model_selector],
        outputs=[num_steps, guidance_scale, model_warning]
    )

    aspect_ratio.change(
        fn=update_dimensions,
        inputs=[aspect_ratio],
        outputs=[width_input, height_input]
    )

    refresh_btn.click(
        fn=refresh_loras,
        outputs=[lora_dropdown]
    )

    generate_btn.click(
        fn=generate_image,
        inputs=[
            prompt_input, model_selector, aspect_ratio, width_input, height_input,
            guidance_scale, num_steps, seed_input, lora_dropdown, lora_scale,
            input_image, img2img_strength
        ],
        outputs=[output_image, status_output]
    )

    prompt_input.submit(
        fn=generate_image,
        inputs=[
            prompt_input, model_selector, aspect_ratio, width_input, height_input,
            guidance_scale, num_steps, seed_input, lora_dropdown, lora_scale,
            input_image, img2img_strength
        ],
        outputs=[output_image, status_output]
    )


if __name__ == "__main__":
    print("DragonFlux Klein - FLUX.2-klein Image Generator")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"LoRA directory: {LORA_DIR}")
    print(f"Device: {device} | Dtype: {dtype}")
    print()

    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
    else:
        print("Warning: CUDA not available, using CPU (very slow)")

    print()
    print("Launching on http://0.0.0.0:8001")
    print("LAN access: http://192.168.7.226:8001")
    print()

    app.launch(
        server_name="0.0.0.0",
        server_port=8001,
        share=False,
        theme=gr.themes.Soft(primary_hue="violet", secondary_hue="gray"),
        css=custom_css,
        head=f'<link rel="icon" href="data:image/svg+xml,{DRAGON_FAVICON.replace("#", "%23").replace(" ", "").replace(chr(10), "")}">'
    )
