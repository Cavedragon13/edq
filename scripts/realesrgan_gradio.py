#!/usr/bin/env python3
"""
Real-ESRGAN Upscaler - Gradio Interface
AI image upscaling with multiple models and face enhancement
Optimized for RTX 5070 Ti (16GB VRAM)
"""

import gradio as gr
import torch
import numpy as np
from pathlib import Path
import os
from datetime import datetime
from PIL import Image
import cv2

# Configuration
OUTPUT_DIR = Path(os.path.expanduser("~/ai_generated/realesrgan"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Available models
MODELS = {
    "RealESRGAN_x4plus": {
        "name": "RealESRGAN x4+ (General)",
        "scale": 4,
        "description": "Best for photos and general images",
    },
    "RealESRGAN_x4plus_anime_6B": {
        "name": "RealESRGAN x4+ Anime",
        "scale": 4,
        "description": "Optimized for anime/illustration",
    },
    "RealESRGAN_x2plus": {
        "name": "RealESRGAN x2+",
        "scale": 2,
        "description": "2x upscaling, faster",
    },
    "realesr-general-x4v3": {
        "name": "Real-ESRGAN General v3",
        "scale": 4,
        "description": "Compact model with denoise options",
    },
}

# Global state
upsampler = None
current_model = None
face_enhancer = None
device = "cuda" if torch.cuda.is_available() else "cpu"

# Dragon favicon as base64 SVG
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
  <text x="32" y="52" text-anchor="middle" fill="#fff" font-size="10" font-weight="bold">UP</text>
</svg>
"""


def load_model(model_name: str):
    """Load Real-ESRGAN model"""
    global upsampler, current_model

    if current_model == model_name and upsampler is not None:
        return f"Model {model_name} already loaded"

    # Clear previous model
    if upsampler is not None:
        del upsampler
        torch.cuda.empty_cache()

    from realesrgan import RealESRGANer
    from basicsr.archs.rrdbnet_arch import RRDBNet

    model_info = MODELS[model_name]
    scale = model_info["scale"]

    # Model URLs for auto-download
    MODEL_URLS = {
        "RealESRGAN_x4plus": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
        "RealESRGAN_x4plus_anime_6B": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth",
        "RealESRGAN_x2plus": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth",
        "realesr-general-x4v3": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth",
    }

    # Configure model architecture based on model name
    if model_name == "RealESRGAN_x4plus":
        model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
        netscale = 4
    elif model_name == "RealESRGAN_x4plus_anime_6B":
        model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=6, num_grow_ch=32, scale=4)
        netscale = 4
    elif model_name == "RealESRGAN_x2plus":
        model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=2)
        netscale = 2
    elif model_name == "realesr-general-x4v3":
        from realesrgan.archs.srvgg_arch import SRVGGNetCompact
        model = SRVGGNetCompact(num_in_ch=3, num_out_ch=3, num_feat=64, num_conv=32, upscale=4, act_type='prelu')
        netscale = 4
    else:
        raise ValueError(f"Unknown model: {model_name}")

    model_path = MODEL_URLS[model_name]

    upsampler = RealESRGANer(
        scale=netscale,
        model_path=model_path,
        dni_weight=None,
        model=model,
        tile=0,  # 0 for no tiling, or set to 256/512 for large images
        tile_pad=10,
        pre_pad=0,
        half=True if device == "cuda" else False,
        gpu_id=0 if device == "cuda" else None,
    )

    current_model = model_name
    return f"Loaded {MODELS[model_name]['name']}"


def load_face_enhancer():
    """Load GFPGAN face enhancer"""
    global face_enhancer

    if face_enhancer is not None:
        return

    from gfpgan import GFPGANer

    face_enhancer = GFPGANer(
        model_path='https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.3.pth',
        upscale=1,
        arch='clean',
        channel_multiplier=2,
        bg_upsampler=upsampler
    )


def upscale_image(
    image: Image.Image,
    model_name: str,
    output_scale: float,
    face_enhance: bool,
    tile_size: int,
    denoise_strength: float,
) -> tuple[Image.Image, str]:
    """Upscale an image using Real-ESRGAN"""
    global upsampler, face_enhancer

    if image is None:
        return None, "Please upload an image"

    # Load model if needed
    load_msg = load_model(model_name)
    print(load_msg)

    # Update tile size
    upsampler.tile = tile_size

    # Convert PIL to numpy (BGR for OpenCV)
    img_np = np.array(image)
    if len(img_np.shape) == 2:  # Grayscale
        img_np = cv2.cvtColor(img_np, cv2.COLOR_GRAY2BGR)
    elif img_np.shape[2] == 4:  # RGBA
        img_np = cv2.cvtColor(img_np, cv2.COLOR_RGBA2BGR)
    else:  # RGB
        img_np = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

    try:
        if face_enhance:
            load_face_enhancer()
            _, _, output = face_enhancer.enhance(
                img_np,
                has_aligned=False,
                only_center_face=False,
                paste_back=True,
                weight=0.5
            )
        else:
            output, _ = upsampler.enhance(img_np, outscale=output_scale)

        # Convert back to RGB
        output_rgb = cv2.cvtColor(output, cv2.COLOR_BGR2RGB)
        output_pil = Image.fromarray(output_rgb)

        # Save output
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        input_size = f"{image.width}x{image.height}"
        output_size = f"{output_pil.width}x{output_pil.height}"
        filename = f"upscaled_{timestamp}_{input_size}_to_{output_size}.png"
        output_path = OUTPUT_DIR / filename
        output_pil.save(output_path, "PNG")

        status = f"Upscaled from {input_size} to {output_size}\nSaved to: {output_path}"
        return output_pil, status

    except Exception as e:
        return None, f"Error: {str(e)}"


def create_interface():
    """Create the Gradio interface"""

    with gr.Blocks(title="Real-ESRGAN Upscaler") as demo:
        gr.HTML(f"""
        <div style="text-align: center; margin-bottom: 1rem;">
            <div style="display: inline-block; width: 48px; height: 48px; margin-bottom: 0.5rem;">
                {DRAGON_FAVICON}
            </div>
            <h1 style="margin: 0;">Real-ESRGAN Upscaler</h1>
            <p style="color: #666; margin: 0.5rem 0;">AI Image Upscaling with Face Enhancement</p>
        </div>
        """)

        with gr.Row():
            with gr.Column(scale=1):
                input_image = gr.Image(
                    label="Input Image",
                    type="pil",
                    sources=["upload", "clipboard"],
                )

                model_dropdown = gr.Dropdown(
                    choices=list(MODELS.keys()),
                    value="RealESRGAN_x4plus",
                    label="Model",
                    info="Choose upscaling model",
                )

                # Model info display
                model_info = gr.Markdown(
                    value=f"**{MODELS['RealESRGAN_x4plus']['name']}**: {MODELS['RealESRGAN_x4plus']['description']}"
                )

                output_scale = gr.Slider(
                    minimum=1,
                    maximum=8,
                    value=4,
                    step=0.5,
                    label="Output Scale",
                    info="Final upscale factor (model scale * this value)",
                )

                tile_size = gr.Slider(
                    minimum=0,
                    maximum=512,
                    value=0,
                    step=64,
                    label="Tile Size",
                    info="0 = no tiling (faster), 256/512 for large images (saves VRAM)",
                )

                face_enhance = gr.Checkbox(
                    label="Face Enhancement (GFPGAN)",
                    value=False,
                    info="Enhance faces in the image",
                )

                denoise_strength = gr.Slider(
                    minimum=0,
                    maximum=1,
                    value=0.5,
                    step=0.1,
                    label="Denoise Strength",
                    info="Only for realesr-general-x4v3 model",
                    visible=False,
                )

                upscale_btn = gr.Button("Upscale", variant="primary", size="lg")

            with gr.Column(scale=1):
                output_image = gr.Image(
                    label="Output Image",
                    type="pil",
                    interactive=False,
                )

                status_text = gr.Textbox(
                    label="Status",
                    interactive=False,
                    lines=3,
                )

        # Update model info when model changes
        def update_model_info(model_name):
            info = MODELS[model_name]
            show_denoise = model_name == "realesr-general-x4v3"
            return (
                f"**{info['name']}**: {info['description']}",
                gr.update(visible=show_denoise)
            )

        model_dropdown.change(
            fn=update_model_info,
            inputs=[model_dropdown],
            outputs=[model_info, denoise_strength],
        )

        # Upscale button click
        upscale_btn.click(
            fn=upscale_image,
            inputs=[
                input_image,
                model_dropdown,
                output_scale,
                face_enhance,
                tile_size,
                denoise_strength,
            ],
            outputs=[output_image, status_text],
        )

        gr.HTML(f"""
        <div style="text-align: center; margin-top: 1rem; padding: 1rem; background: #f0fdf4; border-radius: 8px;">
            <p style="margin: 0; color: #166534;">
                <strong>Output directory:</strong> ~/ai_generated/realesrgan/
            </p>
        </div>
        """)

    return demo


if __name__ == "__main__":
    print("Loading Real-ESRGAN Upscaler...")
    print(f"Device: {device}")
    print(f"Output directory: {OUTPUT_DIR}")

    demo = create_interface()
    demo.launch(
        server_name="0.0.0.0",
        server_port=8010,
        share=False,
        show_error=True,
        theme=gr.themes.Soft(primary_hue="emerald", secondary_hue="blue"),
        css="""
        .gradio-container { max-width: 1200px !important; }
        footer { display: none !important; }
        """,
    )
