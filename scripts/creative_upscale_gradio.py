#!/usr/bin/env python3
"""
Creative Upscaler - FLUX + ControlNet Tile
Prompt-guided creative upscaling with artistic enhancements
Optimized for RTX 5070 Ti (16GB VRAM)
"""

import gradio as gr
import torch
import numpy as np
from pathlib import Path
import os
from datetime import datetime
from PIL import Image
import gc

# Configuration
OUTPUT_DIR = Path(os.path.expanduser("~/ai_generated/creative-upscale"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Global state
pipeline = None
device = "cuda" if torch.cuda.is_available() else "cpu"

# Memory optimization for 16GB VRAM
os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'expandable_segments:True'


def clear_gpu_memory():
    """Clear GPU memory"""
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def load_pipeline():
    """Load FLUX + ControlNet pipeline (lazy loading)"""
    global pipeline

    if pipeline is not None:
        return

    from diffusers import FluxControlNetPipeline, FluxControlNetModel
    from diffusers.utils import load_image

    print("🔄 Loading FLUX + ControlNet Tile...")

    # Load ControlNet
    controlnet = FluxControlNetModel.from_pretrained(
        "alimama-creative/FLUX.1-dev-Controlnet-Upscaler",
        torch_dtype=torch.bfloat16,
        device_map="balanced"
    )

    # Load pipeline
    pipeline = FluxControlNetPipeline.from_pretrained(
        "black-forest-labs/FLUX.1-dev",
        controlnet=controlnet,
        torch_dtype=torch.bfloat16,
        device_map="balanced"
    )

    # Memory optimizations
    pipeline.enable_model_cpu_offload()
    if hasattr(pipeline, 'vae'):
        pipeline.vae.enable_slicing()
        pipeline.vae.enable_tiling()

    print("✓ Pipeline loaded successfully")


def creative_upscale(
    input_image: Image.Image,
    prompt: str,
    scale_factor: int,
    creativity: float,
    steps: int,
    guidance_scale: float,
    progress=gr.Progress()
) -> tuple:
    """
    Perform creative upscaling with prompt guidance.

    Args:
        input_image: Input PIL Image
        prompt: Text prompt to guide upscaling
        scale_factor: Upscale multiplier (2x or 4x)
        creativity: How creative vs faithful (0.0-1.0)
        steps: Inference steps (20-50)
        guidance_scale: Prompt adherence (3.5-15)
    """
    try:
        load_pipeline()
        progress(0.1, desc="Preparing image...")

        # Resize input for controlnet
        width, height = input_image.size
        new_width = width * scale_factor
        new_height = height * scale_factor

        # Ensure dimensions are multiples of 16
        new_width = (new_width // 16) * 16
        new_height = (new_height // 16) * 16

        progress(0.2, desc="Generating...")

        # ControlNet strength (inverse of creativity)
        # More creativity = less faithful to original
        controlnet_strength = 1.0 - (creativity * 0.5)

        # Generate
        result = pipeline(
            prompt=prompt,
            control_image=input_image,
            width=new_width,
            height=new_height,
            controlnet_conditioning_scale=controlnet_strength,
            num_inference_steps=steps,
            guidance_scale=guidance_scale,
            generator=torch.Generator(device=device).manual_seed(42)
        ).images[0]

        progress(0.9, desc="Saving...")

        # Save output
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"creative_upscale_{scale_factor}x_{timestamp}.png"
        output_path = OUTPUT_DIR / filename
        result.save(output_path, format="PNG", optimize=True)

        clear_gpu_memory()

        info = (
            f"✓ Creative upscale complete!\n"
            f"Output: {scale_factor}x ({new_width}x{new_height})\n"
            f"Creativity: {creativity:.1f}\n"
            f"Saved: {filename}"
        )

        return result, info

    except Exception as e:
        clear_gpu_memory()
        return None, f"❌ Error: {str(e)}"


# Gradio Interface
with gr.Blocks(
    title="Creative Upscaler - FLUX + ControlNet",
    theme=gr.themes.Soft(primary_hue="emerald")
) as demo:

    gr.Markdown("""
    # 🎨 Creative Upscaler - FLUX + ControlNet Tile

    Prompt-guided creative upscaling. Unlike traditional upscalers, this uses AI to **add creative details**
    based on your prompt while preserving the original composition.

    **Use cases:**
    - Enhance low-res art with artistic details
    - Add texture and refinement to sketches
    - Upscale with style transformations
    - Creative "reimagining" of images
    """)

    with gr.Row():
        with gr.Column():
            input_image = gr.Image(
                label="Input Image",
                type="pil",
                sources=["upload", "clipboard"],
                height=400
            )

            prompt = gr.Textbox(
                label="Enhancement Prompt",
                placeholder="high quality, detailed, sharp, professional photography, vibrant colors",
                lines=3,
                value="high quality, detailed, sharp, professional photography"
            )

            with gr.Row():
                scale_factor = gr.Slider(
                    minimum=2,
                    maximum=4,
                    step=1,
                    value=2,
                    label="Scale Factor",
                    info="2x = faster, 4x = higher quality"
                )
                creativity = gr.Slider(
                    minimum=0.0,
                    maximum=1.0,
                    step=0.1,
                    value=0.3,
                    label="Creativity",
                    info="0 = faithful, 1 = very creative"
                )

            with gr.Accordion("Advanced Settings", open=False):
                steps = gr.Slider(
                    minimum=20,
                    maximum=50,
                    step=5,
                    value=30,
                    label="Inference Steps",
                    info="More = better quality but slower"
                )
                guidance_scale = gr.Slider(
                    minimum=3.5,
                    maximum=15.0,
                    step=0.5,
                    value=7.5,
                    label="Guidance Scale",
                    info="How closely to follow the prompt"
                )

            upscale_btn = gr.Button("🚀 Creative Upscale", variant="primary", size="lg")

        with gr.Column():
            output_image = gr.Image(label="Upscaled Result", height=400)
            output_info = gr.Textbox(label="Status", lines=4)

    # Examples
    gr.Examples(
        examples=[
            ["A sketch of a dragon", 2, 0.5, 30, 7.5],
            ["professional portrait photography, studio lighting", 2, 0.2, 30, 7.5],
            ["vibrant fantasy art, detailed, magical atmosphere", 4, 0.7, 40, 10.0],
        ],
        inputs=[prompt, scale_factor, creativity, steps, guidance_scale],
        label="Example Prompts"
    )

    # Event handlers
    upscale_btn.click(
        fn=creative_upscale,
        inputs=[input_image, prompt, scale_factor, creativity, steps, guidance_scale],
        outputs=[output_image, output_info],
        show_progress="full"
    )

    gr.Markdown("""
    ---
    **Tips:**
    - **Low creativity (0-0.3):** Faithful upscaling with minor enhancements
    - **Medium creativity (0.4-0.6):** Add artistic details and improvements
    - **High creativity (0.7-1.0):** Creative reimagining (may diverge from original)

    **GPU Usage:** Closes other services if VRAM is tight (~14GB peak for 4x upscale)

    **Output:** `~/ai_generated/creative-upscale/`
    """)


if __name__ == "__main__":
    print("🎨 Starting Creative Upscaler...")
    print(f"Device: {device}")
    print(f"Output: {OUTPUT_DIR}")
    print("\n✓ Access at: http://192.168.7.226:8018")

    demo.queue().launch(
        server_name="0.0.0.0",
        server_port=8018,
        share=False,
        show_error=True
    )
