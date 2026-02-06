#!/usr/bin/env python3
"""
Z-Image Base - Gradio Interface
Alibaba Tongyi's 6B parameter text-to-image model with CFG and negative prompt support
Optimized for RTX 5070 Ti (16GB VRAM)
"""

import gradio as gr
import torch
from pathlib import Path
import os
from datetime import datetime
from PIL import Image

# Configuration
MODEL_ID = "Tongyi-MAI/Z-Image"
OUTPUT_DIR = Path(os.path.expanduser("~/ai_generated/zimage"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# LoRA directory
LORA_DIR = Path(os.path.expanduser("~/models/loras/zimage"))
LORA_DIR.mkdir(parents=True, exist_ok=True)

# Aspect ratio presets
ASPECT_RATIOS = {
    "1:1 (1024x1024)": (1024, 1024),
    "9:16 Portrait (576x1024)": (576, 1024),
    "16:9 Landscape (1024x576)": (1024, 576),
    "3:4 Portrait (768x1024)": (768, 1024),
    "4:3 Landscape (1024x768)": (1024, 768),
    "2:3 Portrait (680x1024)": (680, 1024),
    "3:2 Landscape (1024x680)": (1024, 680),
    "Custom": None,
}

# Global pipeline state
pipe = None
loaded_loras = []
device = "cuda" if torch.cuda.is_available() else "cpu"
dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32

# Dragon favicon
DRAGON_FAVICON = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <defs>
    <linearGradient id="dragonGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#10B981"/>
      <stop offset="100%" style="stop-color:#3B82F6"/>
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
    """Scan LoRA directory for available files"""
    lora_files = []
    if LORA_DIR.exists():
        for ext in ["*.safetensors", "*.bin", "*.pt"]:
            lora_files.extend(LORA_DIR.glob(ext))
            lora_files.extend(LORA_DIR.glob(f"**/{ext}"))

    loras = ["None"]
    for f in sorted(set(lora_files)):
        try:
            rel_path = f.relative_to(LORA_DIR)
            loras.append(str(rel_path))
        except ValueError:
            loras.append(f.name)
    return loras


def load_pipeline():
    """Lazy load the Z-Image pipeline with memory optimizations"""
    global pipe

    if pipe is not None:
        return pipe

    print(f"Loading Z-Image Base model...")
    try:
        from diffusers import ZImagePipeline

        # Memory optimization (expandable_segments is superior to max_split_size_mb)
        os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

        pipe = ZImagePipeline.from_pretrained(MODEL_ID, torch_dtype=dtype)

        # Use sequential CPU offload to fit in 16GB VRAM
        pipe.enable_sequential_cpu_offload()

        # VAE optimizations
        if hasattr(pipe, 'vae'):
            pipe.vae.enable_slicing()
            pipe.vae.enable_tiling()

        print("Z-Image Base loaded with CPU offloading + VAE optimizations")
    except Exception as e:
        print(f"Failed to load model: {e}")
        raise
    return pipe


def apply_lora(lora_name, lora_scale=1.0):
    """Load and apply a LoRA"""
    global pipe, loaded_loras

    if pipe is None:
        return "Load model first"

    if lora_name == "None" or not lora_name:
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
        if loaded_loras:
            pipe.unload_lora_weights()

        pipe.load_lora_weights(str(lora_path))
        loaded_loras = [lora_name]
        return f"LoRA loaded: {lora_name} (scale: {lora_scale})"
    except Exception as e:
        return f"Error loading LoRA: {e}"


def generate_image(
    prompt: str,
    negative_prompt: str,
    aspect_ratio: str,
    width: int,
    height: int,
    guidance_scale: float,
    num_inference_steps: int,
    seed: int,
    lora_name: str,
    lora_scale: float,
    progress=gr.Progress()
):
    """Generate an image from text prompt"""
    if not prompt or prompt.strip() == "":
        return None, "Please enter a prompt"

    progress(0, desc="Loading model...")
    try:
        pipeline = load_pipeline()
    except Exception as e:
        return None, f"Failed to load model: {str(e)}"

    # Apply LoRA if selected
    if lora_name and lora_name != "None":
        progress(0.1, desc="Loading LoRA...")
        lora_status = apply_lora(lora_name, lora_scale)
        print(lora_status)

    # Get dimensions
    if aspect_ratio != "Custom" and aspect_ratio in ASPECT_RATIOS:
        dims = ASPECT_RATIOS[aspect_ratio]
        if dims:
            width, height = dims

    # Handle seed
    if seed == -1:
        seed = torch.randint(0, 2**32, (1,)).item()
    generator = torch.Generator(device="cpu").manual_seed(int(seed))

    progress(0.2, desc="Generating image...")
    try:
        gen_kwargs = {
            "prompt": prompt,
            "height": height,
            "width": width,
            "guidance_scale": guidance_scale,
            "num_inference_steps": num_inference_steps,
            "generator": generator,
        }

        # Add negative prompt if provided (Z-Image Base supports this)
        if negative_prompt and negative_prompt.strip():
            gen_kwargs["negative_prompt"] = negative_prompt

        # Add LoRA scale
        if loaded_loras and lora_scale != 1.0:
            gen_kwargs["cross_attention_kwargs"] = {"scale": lora_scale}

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
        neg_info = f"\nNegative: {negative_prompt[:50]}..." if negative_prompt and negative_prompt.strip() else ""
        progress(1.0, desc="Done!")
        return image, f"Generated | {width}x{height} | CFG: {guidance_scale} | Steps: {num_inference_steps}\nSaved: {filepath}\nSeed: {seed}{lora_info}{neg_info}"

    except torch.cuda.OutOfMemoryError:
        return None, "Out of GPU memory. Try a smaller resolution."
    except Exception as e:
        return None, f"Generation failed: {str(e)}"


def refresh_loras():
    """Refresh the LoRA dropdown"""
    return gr.update(choices=get_available_loras())


def update_dimensions(aspect_ratio):
    """Update width/height based on aspect ratio"""
    if aspect_ratio == "Custom":
        return gr.update(interactive=True), gr.update(interactive=True)
    elif aspect_ratio in ASPECT_RATIOS and ASPECT_RATIOS[aspect_ratio]:
        w, h = ASPECT_RATIOS[aspect_ratio]
        return gr.update(value=w, interactive=False), gr.update(value=h, interactive=False)
    return gr.update(interactive=True), gr.update(interactive=True)


# Custom CSS
custom_css = """
.gradio-container {
    max-width: 1400px !important;
}
.dragon-header {
    text-align: center;
    background: linear-gradient(135deg, #10B981 0%, #3B82F6 100%);
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
with gr.Blocks(title="Z-Image Base") as app:

    gr.HTML('<div class="dragon-header">Z-Image Base</div>')
    gr.HTML('<div class="dragon-subtitle">Alibaba Tongyi 6B Text-to-Image with CFG + Negative Prompts</div>')

    with gr.Row():
        with gr.Column(scale=1):
            # Prompt
            prompt_input = gr.Textbox(
                label="Prompt",
                placeholder="A majestic dragon with emerald scales perched on a mountain peak at sunset...",
                lines=3
            )

            # Negative prompt (Z-Image Base feature!)
            negative_prompt = gr.Textbox(
                label="Negative Prompt",
                placeholder="blurry, low quality, distorted, deformed, ugly, bad anatomy...",
                lines=2
            )

            # Aspect ratio
            with gr.Row():
                aspect_ratio = gr.Dropdown(
                    choices=list(ASPECT_RATIOS.keys()),
                    value="1:1 (1024x1024)",
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
                    label="LoRA Scale"
                )

                gr.Markdown(f"Place LoRA files in: `{LORA_DIR}`")

            # Advanced settings
            with gr.Accordion("Advanced Settings", open=False):
                guidance_scale = gr.Slider(
                    minimum=1.0, maximum=15.0, value=7.0, step=0.5,
                    label="CFG Scale",
                    info="Higher = closer to prompt (7-10 recommended)"
                )
                num_steps = gr.Slider(
                    minimum=10, maximum=50, value=30, step=1,
                    label="Inference Steps",
                    info="More steps = higher quality (30 default)"
                )
                seed_input = gr.Number(
                    value=-1,
                    label="Seed",
                    info="-1 for random"
                )

            generate_btn = gr.Button("Generate", variant="primary", size="lg")

        with gr.Column(scale=1):
            output_image = gr.Image(label="Generated Image", type="pil")
            status_output = gr.Textbox(label="Status", lines=4, interactive=False)

    # Example prompts
    gr.Examples(
        examples=[
            ["A majestic dragon with emerald scales perched on a mountain peak, golden sunset lighting", "blurry, low quality, deformed"],
            ["Portrait of an elegant woman with flowing silver hair, photorealistic, studio lighting", "cartoon, anime, ugly, distorted"],
            ["A cyberpunk cityscape at night with neon signs and flying cars, rain-slicked streets", "daytime, sunny, empty streets"],
            ["Enchanted forest with bioluminescent mushrooms and a crystal clear stream", "dark, scary, dead trees"],
            ["A steampunk mechanical dragon made of brass gears and copper pipes", "organic, natural, simple"],
        ],
        inputs=[prompt_input, negative_prompt],
        label="Example Prompts"
    )

    gr.Markdown(f"""
    ---
    **Z-Image Base Features:** CFG scaling, negative prompts, superior photorealism, accurate hands & text rendering

    **Tips:** CFG 7-10 recommended | 30 steps for quality | Negative prompts help refine output

    **Output:** `{OUTPUT_DIR}` | **LoRAs:** `{LORA_DIR}`
    """)

    # Event handlers
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
            prompt_input, negative_prompt, aspect_ratio, width_input, height_input,
            guidance_scale, num_steps, seed_input, lora_dropdown, lora_scale
        ],
        outputs=[output_image, status_output]
    )

    prompt_input.submit(
        fn=generate_image,
        inputs=[
            prompt_input, negative_prompt, aspect_ratio, width_input, height_input,
            guidance_scale, num_steps, seed_input, lora_dropdown, lora_scale
        ],
        outputs=[output_image, status_output]
    )


if __name__ == "__main__":
    print("Z-Image Base - Alibaba Tongyi Text-to-Image Generator")
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
    print("Launching on http://0.0.0.0:8011")
    print("LAN access: http://192.168.7.226:8011")
    print()

    app.launch(
        server_name="0.0.0.0",
        server_port=8011,
        share=False
    )
