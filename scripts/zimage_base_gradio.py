#!/usr/bin/env python3
"""
Z-Image Base + Turbo ControlNet - Gradio Interface
Alibaba Tongyi's 6B parameter text-to-image model with:
- Base model: CFG and negative prompt support
- Turbo model: 8-step fast inference with ControlNet Union 2.1
Optimized for RTX 5070 Ti (16GB VRAM)
"""

import gradio as gr
import torch
from pathlib import Path
import os
import sys
import threading
from datetime import datetime
from PIL import Image
import numpy as np
import cv2

# VideoX-Fun path for ControlNet support
VIDEOX_FUN_PATH = Path("/srv/containers/edq/projects/VideoX-Fun")
if str(VIDEOX_FUN_PATH) not in sys.path:
    sys.path.insert(0, str(VIDEOX_FUN_PATH))

# Configuration
MODEL_ID_BASE = "Tongyi-MAI/Z-Image"
MODEL_ID_TURBO = "Tongyi-MAI/Z-Image-Turbo"
CONTROLNET_MODEL_ID = "alibaba-pai/Z-Image-Turbo-Fun-Controlnet-Union-2.1"
CONTROLNET_WEIGHTS_FILENAME = "Z-Image-Turbo-Fun-Controlnet-Union-2.1.safetensors"
# Config from VideoX-Fun/config/z_image/z_image_control_2.1.yaml
CONTROLNET_TRANSFORMER_KWARGS = {
    "control_layers_places": [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28],
    "control_refiner_layers_places": [0, 1],
    "add_control_noise_refiner": True,
    "add_control_noise_refiner_correctly": True,
    "control_in_dim": 33,
}
OUTPUT_DIR = Path(os.path.expanduser("~/ai_generated/zimage"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# LoRA directory
LORA_DIR = Path(os.path.expanduser("~/models/loras/zimage"))
LORA_DIR.mkdir(parents=True, exist_ok=True)

# ControlNet condition types
CONTROLNET_CONDITIONS = [
    "None",
    "Canny (Edge Detection)",
    "Depth (Depth Maps)",
    "Pose (Human Pose)",
    "HED (Holistic Edges)",
    "MLSD (Line Segments)"
]

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
pipe_base = None
pipe_turbo = None
pipe_control = None
current_model = "Base"
loaded_loras = []
device = "cuda" if torch.cuda.is_available() else "cpu"
dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32

# ControlNet pre-download state
_controlnet_weights_path = None   # set once download completes
_controlnet_download_error = None  # set if download fails


def _prefetch_controlnet_weights():
    """Download ControlNet weights at startup so first generation doesn't block."""
    global _controlnet_weights_path, _controlnet_download_error
    try:
        from huggingface_hub import hf_hub_download
        print(f"[ControlNet] Pre-fetching weights ({CONTROLNET_WEIGHTS_FILENAME})...")
        path = hf_hub_download(
            repo_id=CONTROLNET_MODEL_ID,
            filename=CONTROLNET_WEIGHTS_FILENAME,
        )
        _controlnet_weights_path = path
        print(f"[ControlNet] Weights ready: {path}")
    except Exception as e:
        _controlnet_download_error = str(e)
        print(f"[ControlNet] Pre-fetch failed: {e}")

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


def preprocess_control_image(image: Image.Image, condition_type: str) -> Image.Image:
    """Preprocess control image based on condition type"""
    if condition_type == "None" or not image:
        return None

    # Convert PIL to numpy
    img_array = np.array(image)

    # Convert RGB to BGR for OpenCV
    if len(img_array.shape) == 3 and img_array.shape[2] == 3:
        img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

    if "Canny" in condition_type:
        # Canny edge detection
        gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY) if len(img_array.shape) == 3 else img_array
        edges = cv2.Canny(gray, 50, 150)
        processed = cv2.cvtColor(edges, cv2.COLOR_GRAY2RGB)

    elif "HED" in condition_type:
        # For HED, we'll use Canny as fallback (proper HED requires model)
        gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY) if len(img_array.shape) == 3 else img_array
        edges = cv2.Canny(gray, 100, 200)
        processed = cv2.cvtColor(edges, cv2.COLOR_GRAY2RGB)

    elif "Depth" in condition_type:
        # Simple depth estimation using grayscale
        gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY) if len(img_array.shape) == 3 else img_array
        depth = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
        processed = cv2.cvtColor(depth, cv2.COLOR_GRAY2RGB)

    elif "MLSD" in condition_type:
        # Line segment detection using HoughLines
        gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY) if len(img_array.shape) == 3 else img_array
        edges = cv2.Canny(gray, 50, 150)
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=80, minLineLength=30, maxLineGap=10)
        line_img = np.zeros_like(img_array)
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                cv2.line(line_img, (x1, y1), (x2, y2), (255, 255, 255), 2)
        processed = line_img

    else:
        # Pose or unknown - return original
        processed = cv2.cvtColor(img_array, cv2.COLOR_BGR2RGB) if len(img_array.shape) == 3 else img_array

    return Image.fromarray(processed)


def evict_other_models(keep: str):
    """Unload models not currently needed to free VRAM. keep = 'base'|'turbo'|'control'"""
    global pipe_base, pipe_turbo, pipe_control
    import gc
    if keep != "base" and pipe_base is not None:
        print(f"[VRAM] Evicting Base model to free VRAM for {keep}...")
        pipe_base.to("cpu")
        pipe_base = None
    if keep != "turbo" and pipe_turbo is not None:
        print(f"[VRAM] Evicting Turbo model to free VRAM for {keep}...")
        pipe_turbo.to("cpu") if hasattr(pipe_turbo, 'to') else None
        pipe_turbo = None
    if keep != "control" and pipe_control is not None:
        print(f"[VRAM] Evicting ControlNet model to free VRAM for {keep}...")
        pipe_control.to("cpu") if hasattr(pipe_control, 'to') else None
        pipe_control = None
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()


def load_pipeline(model_type: str = "Base", use_controlnet: bool = False):
    """Lazy load the Z-Image pipeline with memory optimizations"""
    global pipe_base, pipe_turbo, pipe_control, current_model

    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

    if use_controlnet:
        evict_other_models("control")
        return load_control_pipeline()

    if model_type == "Base":
        if pipe_base is not None:
            current_model = "Base"
            return pipe_base

        evict_other_models("base")
        print("Loading Z-Image Base model...")
        try:
            from diffusers import ZImagePipeline
            pipe_base = ZImagePipeline.from_pretrained(MODEL_ID_BASE, torch_dtype=dtype)
            pipe_base.enable_model_cpu_offload()
            if hasattr(pipe_base, 'vae'):
                pipe_base.vae.enable_slicing()
                pipe_base.vae.enable_tiling()
            print("Z-Image Base loaded with model CPU offload + VAE optimizations")
            current_model = "Base"
            return pipe_base
        except Exception as e:
            print(f"Failed to load Base model: {e}")
            raise

    else:  # Turbo
        if pipe_turbo is not None:
            current_model = "Turbo"
            return pipe_turbo

        evict_other_models("turbo")
        print("Loading Z-Image Turbo model...")
        try:
            from diffusers import ZImagePipeline
            pipe_turbo = ZImagePipeline.from_pretrained(MODEL_ID_TURBO, torch_dtype=dtype)
            pipe_turbo.enable_model_cpu_offload()
            if hasattr(pipe_turbo, 'vae'):
                pipe_turbo.vae.enable_slicing()
                pipe_turbo.vae.enable_tiling()
            print("Z-Image Turbo loaded with model CPU offload + VAE optimizations")
            current_model = "Turbo"
            return pipe_turbo
        except Exception as e:
            print(f"Failed to load Turbo model: {e}")
            raise


def load_control_pipeline():
    """Load Z-Image ControlNet pipeline via VideoX-Fun"""
    global pipe_control, current_model, _controlnet_weights_path, _controlnet_download_error

    if pipe_control is not None:
        current_model = "Control"
        return pipe_control

    # Check pre-fetch state
    if _controlnet_download_error:
        raise RuntimeError(f"ControlNet weights download failed at startup: {_controlnet_download_error}")
    if _controlnet_weights_path is None:
        raise RuntimeError(
            "ControlNet weights are still downloading in the background. "
            "Check the server console for progress — try again in a moment."
        )

    print("Loading Z-Image ControlNet pipeline (VideoX-Fun)...")
    try:
        from huggingface_hub import snapshot_download
        from safetensors.torch import load_file
        from diffusers import FlowMatchEulerDiscreteScheduler
        from videox_fun.models.z_image_transformer2d_control import ZImageControlTransformer2DModel
        from videox_fun.pipeline.pipeline_z_image_control import ZImageControlPipeline
        from diffusers.models.autoencoders import AutoencoderKL
        from transformers import AutoTokenizer, AutoModelForCausalLM

        control_weights_path = _controlnet_weights_path
        print(f"Control weights: {control_weights_path}")

        # Get local cache path for base model
        print("Downloading/locating Turbo base model...")
        model_local_path = snapshot_download(MODEL_ID_TURBO)

        # Load transformer with control architecture
        print("Building control transformer from base weights...")
        transformer = ZImageControlTransformer2DModel.from_pretrained(
            model_local_path,
            subfolder="transformer",
            transformer_additional_kwargs=CONTROLNET_TRANSFORMER_KWARGS,
            low_cpu_mem_usage=True,
            torch_dtype=dtype,
        )

        # Layer control-specific weights on top (strict=False expected — control layers are new)
        print("Loading ControlNet weights...")
        state_dict = load_file(control_weights_path)
        m, u = transformer.load_state_dict(state_dict, strict=False)
        print(f"ControlNet weights loaded: {len(m)} missing, {len(u)} unexpected keys")

        # Load remaining pipeline components from base model
        vae = AutoencoderKL.from_pretrained(model_local_path, subfolder="vae", torch_dtype=dtype)
        tokenizer = AutoTokenizer.from_pretrained(model_local_path, subfolder="tokenizer")
        text_encoder = AutoModelForCausalLM.from_pretrained(
            model_local_path, subfolder="text_encoder", torch_dtype=dtype, low_cpu_mem_usage=True
        )
        scheduler = FlowMatchEulerDiscreteScheduler.from_pretrained(model_local_path, subfolder="scheduler")

        pipe_control = ZImageControlPipeline(
            vae=vae,
            tokenizer=tokenizer,
            text_encoder=text_encoder,
            transformer=transformer,
            scheduler=scheduler,
        )
        pipe_control.enable_model_cpu_offload()

        print("Z-Image ControlNet pipeline ready")
        current_model = "Control"
        return pipe_control
    except Exception as e:
        print(f"Failed to load ControlNet pipeline: {e}")
        raise


def apply_lora(lora_name, lora_scale=1.0):
    """Load and apply a LoRA to the current pipeline"""
    global pipe_base, pipe_turbo, pipe_control, loaded_loras, current_model

    if current_model == "Base":
        pipe = pipe_base
    elif current_model == "Control":
        pipe = pipe_turbo  # LoRA not supported on control pipeline; use turbo for now
    else:
        pipe = pipe_turbo

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
    model_type: str,
    controlnet_condition: str,
    control_image: Image.Image,
    controlnet_scale: float,
    aspect_ratio: str,
    width: int,
    height: int,
    guidance_scale: float,
    num_inference_steps: int,
    seed: int,
    fast_mode: bool,
    lora_name: str,
    lora_scale: float,
    progress=gr.Progress()
):
    """Generate an image from text prompt with optional ControlNet guidance"""
    if not prompt or prompt.strip() == "":
        return None, None, "Please enter a prompt"

    # Validate ControlNet settings
    use_controlnet = controlnet_condition != "None" and control_image is not None
    if use_controlnet and model_type != "Turbo":
        return None, None, "ControlNet is only available with Turbo model"

    progress(0, desc="Loading model...")
    try:
        pipeline = load_pipeline(model_type, use_controlnet)
    except Exception as e:
        return None, None, f"Failed to load model: {str(e)}"

    # Handle Fast Mode: auto-select distilled LoRA
    if fast_mode:
        progress(0.1, desc="Loading Fast Mode LoRA...")
        # Select LoRA based on inference steps
        if num_inference_steps <= 4:
            fast_lora = "Z-Image-Fun-Lora-Distill-4-Steps-2602.safetensors"
        else:
            fast_lora = "Z-Image-Fun-Lora-Distill-8-Steps-2602.safetensors"

        lora_status = apply_lora(fast_lora, lora_scale)
        print(f"Fast Mode: {lora_status}")

        # Override CFG for Fast Mode (distilled)
        guidance_scale = 1.0
    # Apply LoRA if selected (manual mode)
    elif lora_name and lora_name != "None":
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
    generator = torch.Generator(device=device).manual_seed(int(seed))

    # Preprocess control image if using ControlNet
    processed_control = None
    if use_controlnet:
        progress(0.15, desc="Processing control image...")
        processed_control = preprocess_control_image(control_image, controlnet_condition)
        if processed_control:
            processed_control = processed_control.resize((width, height), Image.LANCZOS)

    # Flush VRAM before generation
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()

    progress(0.2, desc="Generating image...")
    try:
        if use_controlnet and processed_control:
            # VideoX-Fun ZImageControlPipeline expects tensor inputs
            ctrl_array = np.array(processed_control.convert("RGB"))
            ctrl_tensor = torch.from_numpy(ctrl_array).unsqueeze(0).permute(0, 3, 1, 2).float().to(device) / 255.0
            inpaint_image = torch.zeros([1, 3, height, width], device=device)
            mask_image_t = torch.ones([1, 1, height, width], device=device) * 255

            gen_kwargs = {
                "prompt": prompt,
                "negative_prompt": negative_prompt if negative_prompt and negative_prompt.strip() else "",
                "height": height,
                "width": width,
                "num_inference_steps": num_inference_steps,
                "guidance_scale": guidance_scale,
                "generator": generator,
                "control_image": ctrl_tensor,
                "image": inpaint_image,
                "mask_image": mask_image_t,
                "control_context_scale": controlnet_scale,
            }
        else:
            gen_kwargs = {
                "prompt": prompt,
                "height": height,
                "width": width,
                "num_inference_steps": num_inference_steps,
                "generator": generator,
            }

            if model_type == "Turbo" and num_inference_steps == 8:
                gen_kwargs["guidance_scale"] = 1.0
            else:
                gen_kwargs["guidance_scale"] = guidance_scale

            if negative_prompt and negative_prompt.strip() and not (model_type == "Turbo" and num_inference_steps == 8):
                gen_kwargs["negative_prompt"] = negative_prompt

            if loaded_loras and lora_scale != 1.0:
                gen_kwargs["cross_attention_kwargs"] = {"scale": lora_scale}

        result = pipeline(**gen_kwargs)
        image = result.images[0]

        # Save image
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_prompt = "".join(c for c in prompt[:50] if c.isalnum() or c in " -_").strip()
        safe_prompt = safe_prompt.replace(" ", "_")
        model_suffix = f"_{model_type.lower()}"
        controlnet_suffix = f"_cn-{controlnet_condition.split()[0].lower()}" if use_controlnet else ""
        lora_suffix = f"_lora-{Path(lora_name).stem}" if lora_name and lora_name != "None" else ""
        filename = f"{timestamp}_{safe_prompt}{model_suffix}{controlnet_suffix}{lora_suffix}.png"
        filepath = OUTPUT_DIR / filename
        image.save(filepath)

        # Build status message
        model_info = f"{model_type} model"
        if use_controlnet:
            model_info += f" + {controlnet_condition} (scale: {controlnet_scale})"
        lora_info = f"\nLoRA: {lora_name} (scale: {lora_scale})" if loaded_loras else ""
        neg_info = f"\nNegative: {negative_prompt[:50]}..." if negative_prompt and negative_prompt.strip() and gen_kwargs.get("negative_prompt") else ""

        progress(1.0, desc="Done!")
        status_msg = f"Generated | {model_info}\n{width}x{height} | CFG: {gen_kwargs['guidance_scale']} | Steps: {num_inference_steps}\nSaved: {filepath}\nSeed: {seed}{lora_info}{neg_info}"

        return image, processed_control, status_msg

    except torch.cuda.OutOfMemoryError:
        return None, None, "Out of GPU memory. Try a smaller resolution or close other GPU services."
    except Exception as e:
        import traceback
        traceback.print_exc()
        return None, None, f"Generation failed: {str(e)}"


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


def update_model_settings(model_type):
    """Update UI settings when model type changes"""
    if model_type == "Turbo":
        return {
            num_steps: gr.update(value=8, info="Turbo: 8 steps recommended for fast inference"),
            guidance_scale: gr.update(value=1.0, info="Turbo 8-step: Fixed at 1.0 (CFG disabled)"),
            negative_prompt: gr.update(info="Not used in Turbo 8-step mode"),
        }
    else:  # Base
        return {
            num_steps: gr.update(value=30, info="Base: 30 steps default for quality"),
            guidance_scale: gr.update(value=7.0, info="Base: 7-10 recommended"),
            negative_prompt: gr.update(info="Helps refine output and avoid unwanted elements"),
        }


def toggle_control_output(controlnet_condition):
    """Show/hide processed control image output"""
    return gr.update(visible=(controlnet_condition != "None"))


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
with gr.Blocks(title="Z-Image Base + Turbo ControlNet") as app:

    gr.HTML('<div class="dragon-header">Z-Image Base + Turbo ControlNet</div>')
    gr.HTML('<div class="dragon-subtitle">Alibaba Tongyi 6B Text-to-Image | Base (30-step CFG) or Turbo (8-step + ControlNet Union 2.1)</div>')

    with gr.Row():
        with gr.Column(scale=1):
            # Prompt
            prompt_input = gr.Textbox(
                label="Prompt",
                placeholder="A majestic dragon with emerald scales perched on a mountain peak at sunset...",
                lines=3
            )

            # Negative prompt (Base model feature)
            negative_prompt = gr.Textbox(
                label="Negative Prompt (Base model only)",
                placeholder="blurry, low quality, distorted, deformed, ugly, bad anatomy...",
                lines=2
            )

            generate_btn = gr.Button("Generate", variant="primary", size="lg")

            # ControlNet section (Turbo only) - powered by VideoX-Fun
            with gr.Accordion("ControlNet Settings (Turbo only)", open=False):
                gr.Markdown("""
                **ControlNet Union 2.1** — powered by [VideoX-Fun](https://github.com/aigc-apps/VideoX-Fun).
                Select a condition type and upload a reference image. Works with Turbo model only.
                Control weights download automatically on first use (~2 GB).
                """)

                controlnet_condition = gr.Dropdown(
                    choices=CONTROLNET_CONDITIONS,
                    value="None",
                    label="Control Condition",
                    info="Select condition type then upload reference image (Turbo model only)"
                )

                control_image = gr.Image(
                    label="Control Reference Image",
                    type="pil",
                    sources=["upload", "clipboard"],
                )

                controlnet_scale = gr.Slider(
                    minimum=0.0, maximum=1.0, value=0.9, step=0.05,
                    label="ControlNet Scale",
                    info="0.65–1.0 recommended (0.9 default)"
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
                # Fast Mode option
                fast_mode = gr.Checkbox(
                    label="⚡ Fast Mode (Distilled LoRA)",
                    value=False,
                    info="Auto-select 4-step or 8-step distilled LoRA for faster generation"
                )

                gr.Markdown("""
                **Fast Mode:** Uses Z-Image-Fun-Lora-Distill for 4-8x faster generation
                - 4-step or 8-step inference (vs 30 steps)
                - CFG fixed at 1.0 (distilled out)
                - Maintains compatibility with other LoRAs
                - Recommended: LoRA scale 0.7-0.8
                """)

                with gr.Row():
                    lora_dropdown = gr.Dropdown(
                        choices=get_available_loras(),
                        value="None",
                        label="Manual LoRA (disabled when Fast Mode active)",
                        scale=3
                    )
                    refresh_btn = gr.Button("Refresh", scale=1, size="sm")

                lora_scale = gr.Slider(
                    minimum=0.0, maximum=2.0, value=0.8, step=0.05,
                    label="LoRA Scale",
                    info="Recommended: 0.7-0.8 for Fast Mode"
                )

                gr.Markdown(f"Place LoRA files in: `{LORA_DIR}`")

            # Advanced settings
            with gr.Accordion("Advanced Settings", open=False):
                guidance_scale = gr.Slider(
                    minimum=1.0, maximum=15.0, value=7.0, step=0.5,
                    label="CFG Scale",
                    info="Base: 7-10 recommended | Turbo: Fixed at 1.0 for 8-step mode"
                )
                num_steps = gr.Slider(
                    minimum=1, maximum=50, value=30, step=1,
                    label="Inference Steps",
                    info="Base: 30 default | Turbo: 8 recommended for fast inference"
                )
                seed_input = gr.Number(
                    value=-1,
                    label="Seed",
                    info="-1 for random"
                )

            # Model selector (rarely changed)
            model_type = gr.Radio(
                choices=["Base", "Turbo"],
                value="Base",
                label="Model",
                info="Base: 30-step with CFG and negative prompts | Turbo: 8-step fast inference with ControlNet"
            )

        with gr.Column(scale=1):
            output_image = gr.Image(label="Generated Image", type="pil")
            processed_control_output = gr.Image(label="Processed Control Image", type="pil", visible=False)
            status_output = gr.Textbox(label="Status", lines=6, interactive=False)

    # Example prompts
    gr.Examples(
        examples=[
            ["A majestic dragon with emerald scales perched on a mountain peak, golden sunset lighting", "blurry, low quality, deformed", "Base"],
            ["Portrait of an elegant woman with flowing silver hair, photorealistic, studio lighting", "cartoon, anime, ugly, distorted", "Base"],
            ["A cyberpunk cityscape at night with neon signs and flying cars, rain-slicked streets", "", "Turbo"],
            ["Enchanted forest with bioluminescent mushrooms and a crystal clear stream", "", "Turbo"],
            ["A steampunk mechanical dragon made of brass gears and copper pipes", "organic, natural, simple", "Base"],
        ],
        inputs=[prompt_input, negative_prompt, model_type],
        label="Example Prompts"
    )

    gr.Markdown(f"""
    ---
    ### Models

    **✅ Base (Tongyi-MAI/Z-Image)**  30-step CFG · negative prompts · superior photorealism · ~20–30s

    **✅ Turbo (Tongyi-MAI/Z-Image-Turbo)**  8-step fast inference · CFG=1.0 · ~5–10s

    **✅ ControlNet Union 2.1 (Turbo + VideoX-Fun)**  Canny · Depth · Pose · HED · MLSD · 15 control layers · weights auto-download on first use

    **✅ LoRAs**  9 models available in `{LORA_DIR}` · Fast Mode uses distilled 4/8-step LoRAs

    **Output:** `{OUTPUT_DIR}`

    **Resources:**
    - [Z-Image Base](https://huggingface.co/Tongyi-MAI/Z-Image) | [Z-Image Turbo](https://huggingface.co/Tongyi-MAI/Z-Image-Turbo)
    - [ControlNet Union 2.1 weights](https://huggingface.co/alibaba-pai/Z-Image-Turbo-Fun-Controlnet-Union-2.1)
    - [VideoX-Fun repo](https://github.com/aigc-apps/VideoX-Fun) | [Z-Image Blog](https://gaga.art/blog/z-image-base/)
    """)

    # Event handlers
    model_type.change(
        fn=update_model_settings,
        inputs=[model_type],
        outputs=[num_steps, guidance_scale, negative_prompt]
    )

    aspect_ratio.change(
        fn=update_dimensions,
        inputs=[aspect_ratio],
        outputs=[width_input, height_input]
    )

    controlnet_condition.change(
        fn=toggle_control_output,
        inputs=[controlnet_condition],
        outputs=[processed_control_output]
    )

    refresh_btn.click(
        fn=refresh_loras,
        outputs=[lora_dropdown]
    )

    generate_btn.click(
        fn=generate_image,
        inputs=[
            prompt_input, negative_prompt, model_type, controlnet_condition, control_image, controlnet_scale,
            aspect_ratio, width_input, height_input,
            guidance_scale, num_steps, seed_input, fast_mode, lora_dropdown, lora_scale
        ],
        outputs=[output_image, processed_control_output, status_output]
    )

    prompt_input.submit(
        fn=generate_image,
        inputs=[
            prompt_input, negative_prompt, model_type, controlnet_condition, control_image, controlnet_scale,
            aspect_ratio, width_input, height_input,
            guidance_scale, num_steps, seed_input, fast_mode, lora_dropdown, lora_scale
        ],
        outputs=[output_image, processed_control_output, status_output]
    )


if __name__ == "__main__":
    # Start ControlNet weights pre-fetch in background so first generation doesn't block
    threading.Thread(target=_prefetch_controlnet_weights, daemon=True).start()

    print("=" * 80)
    print("Z-Image Base + Turbo ControlNet - Alibaba Tongyi Text-to-Image Generator")
    print("=" * 80)
    print()
    print("Available Models:")
    print(f"  • Base Model: {MODEL_ID_BASE}")
    print(f"    - 30-step inference with CFG and negative prompts")
    print(f"    - Superior photorealism and text rendering")
    print()
    print(f"  • Turbo Model: {MODEL_ID_TURBO}")
    print(f"    - 8-step fast inference (4x faster)")
    print(f"    - ControlNet Union 2.1 with multi-condition support")
    print(f"    - Conditions: Canny, Depth, Pose, HED, MLSD")
    print()
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"LoRA directory: {LORA_DIR}")
    print(f"Device: {device} | Dtype: {dtype}")
    print()

    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
        print()
        print("NOTE: Models use sequential CPU offloading to fit in 16GB VRAM")
        print("      Close other GPU services if you encounter OOM errors")
    else:
        print("⚠️  WARNING: CUDA not available, using CPU (very slow)")

    print()
    print("=" * 80)
    print("Launching on http://0.0.0.0:8011")
    print("LAN access: http://192.168.7.226:8011")
    print("=" * 80)
    print()

    app.launch(
        server_name="0.0.0.0",
        server_port=8011,
        share=False,
        show_error=True,
        favicon_path="/srv/containers/edq/media/favicons/zimage.svg",
        css=custom_css
    )
