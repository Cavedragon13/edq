#!/usr/bin/env python3
"""
Street View Studio — Fetch + AI Transform
Port 8040 | Google Maps Street View + FLUX.1-schnell (local, Apache 2.0)

Requirements:
  - STREET_VIEW_API_KEY in /srv/containers/edq/.env
    Must have "Street View Static API" enabled in Google Cloud Console.
  - FLUX.1-schnell downloaded to /srv/containers/edq/models/flux1-schnell/
    Run: bash scripts/download_flux1_schnell.sh
"""

import os
import sys
import requests
import gradio as gr
from pathlib import Path
from datetime import datetime
from PIL import Image
from io import BytesIO
from dotenv import load_dotenv

load_dotenv("/srv/containers/edq/.env")
GOOGLE_API_KEY = os.getenv("STREET_VIEW_API_KEY") or os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    print("❌ STREET_VIEW_API_KEY not found in /srv/containers/edq/.env")
    print("   Add a Google Maps Platform key with 'Street View Static API' enabled.")
    sys.exit(1)

MODEL_PATH = "/srv/containers/edq/models/flux1-schnell"
if not Path(MODEL_PATH).joinpath("model_index.json").exists():
    print(f"❌ FLUX.1-schnell not found at {MODEL_PATH}")
    print("   Run: bash scripts/download_flux1_schnell.sh")
    sys.exit(1)

STREETVIEW_URL = "https://maps.googleapis.com/maps/api/streetview"
METADATA_URL   = "https://maps.googleapis.com/maps/api/streetview/metadata"

OUTPUT_DIR = Path.home() / "ai_generated" / "streetview_studio"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Presets — (label, prompt) pairs.
# ---------------------------------------------------------------------------
_PRESETS_RAW = [
    ("Custom (type your own below)", ""),
    # Art styles
    ("Watercolor painting",
     "Transform this building into a delicate watercolor painting with soft transparent "
     "washes of color, wet-on-wet blending, and visible paper texture"),
    ("Impressionist oil painting",
     "Convert to an impressionist oil painting with thick expressive brushstrokes, "
     "rich warm color palette, and painterly atmospheric light"),
    ("Pencil sketch",
     "Render as a detailed architectural pencil sketch with fine hatching lines, "
     "precise linework, and shaded volumes on white paper"),
    ("Charcoal drawing",
     "Transform into a bold charcoal drawing with dramatic shadows, gestural strokes, "
     "and rich tonal contrast on textured paper"),
    ("Architect's line rendering",
     "Convert to a professional architectural line rendering with precise clean linework, "
     "minimal shading, white background, and technical drawing aesthetic"),
    # Scene changes
    ("Night scene",
     "Transform into a moody nighttime scene with warm glowing windows, "
     "street lights casting soft pools of light, and a deep blue-black sky"),
    ("Golden hour",
     "Transform into a golden hour scene with warm amber sunlight raking across "
     "the facade, long dramatic shadows, and a glowing orange sky"),
    ("Autumn",
     "Change the season to autumn — warm amber and orange foliage on surrounding trees, "
     "crisp fall light, fallen leaves scattered on the ground"),
    ("Snowy winter",
     "Transform into a winter scene with fresh snow on the roof and windowsills, "
     "bare trees, and pale cool winter light"),
    # Building edits
    ("Remove parked cars",
     "Remove all parked cars and vehicles from in front of the building, "
     "leaving clean empty road and pavement"),
    ("Modern storefront windows",
     "Replace the existing windows with large modern floor-to-ceiling glass shop windows "
     "with elegant minimalist window displays inside"),
    ("Add hanging flower baskets",
     "Add colorful hanging flower baskets filled with bright blooms to the facade, "
     "entrance, and window ledges of the building"),
    ("Fresh white exterior paint",
     "Give the building a fresh coat of crisp clean white paint on the exterior walls "
     "while preserving all original architectural details"),
    ("Cyberpunk",
     "Transform the building into a cyberpunk version with neon signs, holographic "
     "advertisements, rain-slicked neon-lit surfaces, and dramatic night sky"),
]

STYLE_PRESETS = {label: prompt for label, prompt in _PRESETS_RAW}
PRESET_CHOICES = list(STYLE_PRESETS.keys())

# ---------------------------------------------------------------------------
# Lazy-loaded pipeline
# ---------------------------------------------------------------------------
_pipe = None

def get_pipeline():
    global _pipe
    if _pipe is None:
        import torch
        from diffusers import FluxImg2ImgPipeline

        print("⏳ Loading FLUX.1-schnell pipeline (first use)…")
        _pipe = FluxImg2ImgPipeline.from_pretrained(
            MODEL_PATH,
            torch_dtype=torch.bfloat16,
            local_files_only=True,
        )
        _pipe.enable_sequential_cpu_offload()
        if hasattr(_pipe, "vae"):
            _pipe.vae.enable_slicing()
            _pipe.vae.enable_tiling()
        print("✅ Pipeline ready")
    return _pipe


# ---------------------------------------------------------------------------
# Street View fetch
# ---------------------------------------------------------------------------
def fetch_street_view(address, heading_auto, heading, pitch, fov):
    if not address.strip():
        return None, "Please enter an address."

    # Metadata check first — free, no image quota consumed
    try:
        meta = requests.get(METADATA_URL, params={
            "location": address.strip(),
            "key": GOOGLE_API_KEY,
            "source": "outdoor",
        }, timeout=10).json()
    except requests.RequestException as e:
        return None, f"Network error reaching Google Maps: {e}"

    status = meta.get("status", "UNKNOWN")
    if status == "REQUEST_DENIED":
        return None, (
            "❌ API key rejected (REQUEST_DENIED). "
            "Ensure your STREET_VIEW_API_KEY has 'Street View Static API' enabled "
            "in Google Cloud Console → APIs & Services."
        )
    if status != "OK":
        return None, f"No Street View imagery found for '{address}' (status: {status})"

    loc = meta["location"]
    location_str = f"{loc['lat']},{loc['lng']}"

    params = {
        "size": "640x640",
        "location": location_str,
        "key": GOOGLE_API_KEY,
        "source": "outdoor",
        "pitch": int(pitch),
        "fov": int(fov),
        "return_error_code": "true",
    }
    if not heading_auto:
        params["heading"] = int(heading)

    try:
        img_resp = requests.get(STREETVIEW_URL, params=params, timeout=15)
    except requests.RequestException as e:
        return None, f"Network error fetching Street View image: {e}"

    if img_resp.status_code == 404:
        return None, (
            "No Street View imagery at this exact spot. "
            "Try a nearby address or disable 'Auto heading' and adjust the heading."
        )
    if img_resp.status_code != 200:
        return None, f"Street View API returned HTTP {img_resp.status_code}"

    img = Image.open(BytesIO(img_resp.content)).convert("RGB")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_addr = "".join(c if c.isalnum() else "_" for c in address)[:30]
    out_path = OUTPUT_DIR / f"sv_{safe_addr}_{timestamp}.jpg"
    img.save(str(out_path), quality=92)

    date_str = meta.get("date", "date unknown")
    head_str = "auto" if heading_auto else f"{int(heading)}°"
    pano_id  = meta.get("pano_id", "")
    info = (
        f"📍 {loc['lat']:.5f}, {loc['lng']:.5f}  ·  {date_str}  ·  "
        f"heading {head_str}  ·  fov {int(fov)}°"
    )
    if pano_id:
        info += f"  ·  pano {pano_id[:10]}…"
    info += f"\n💾 {out_path}"

    return img, info


# ---------------------------------------------------------------------------
# AI Transform — local FLUX.1-schnell img2img
# ---------------------------------------------------------------------------
def transform_image(sv_img, preset, custom_prompt, strength, steps, seed, randomize):
    if sv_img is None:
        return None, "Fetch a Street View image first."

    base  = STYLE_PRESETS.get(preset, "") or ""
    extra = (custom_prompt or "").strip()
    if preset == "Custom (type your own below)":
        prompt = extra
    elif extra:
        prompt = f"{base}. {extra}"
    else:
        prompt = base

    if not prompt:
        return None, "Enter a prompt or select a preset."

    yield None, "⏳ Loading pipeline…"

    try:
        import torch
        import random as _random

        pipe = get_pipeline()

        if isinstance(sv_img, Image.Image):
            input_img = sv_img.convert("RGB")
        else:
            input_img = Image.fromarray(sv_img).convert("RGB")

        actual_seed = _random.randint(0, 2**32 - 1) if randomize else int(seed)
        generator = torch.Generator().manual_seed(actual_seed)

        yield None, f"⏳ Generating — seed {actual_seed}…"

        result = pipe(
            prompt=prompt,
            image=input_img,
            strength=float(strength),
            num_inference_steps=int(steps),
            guidance_scale=0.0,   # schnell is guidance-distilled
            generator=generator,
        )
        out_img = result.images[0]

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = OUTPUT_DIR / f"transformed_{timestamp}_s{actual_seed}.jpg"
        out_img.save(str(out_path), quality=92)

        yield out_img, f"✅ Done  ·  seed {actual_seed}  ·  {out_path}"

    except Exception as e:
        yield None, f"❌ Error: {e}"


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
CSS = """
body, .gradio-container { background: #1a1a2e !important; color: #e0e0e0 !important; }
.dark-header { background: #16213e; padding: 16px 20px; border-radius: 8px; margin-bottom: 12px; }
.dark-header h1 { color: #7c9cbf; margin: 0; font-size: 1.4em; }
.dark-header p  { color: #9ca3af; margin: 4px 0 0; font-size: 0.85em; }
.section-label { color: #7c9cbf !important; font-weight: 700 !important;
                 font-size: 0.75em !important; text-transform: uppercase !important;
                 letter-spacing: 0.08em !important; margin: 4px 0 !important; }
label { color: #9ca3af !important; }
.gr-button-primary { background: #3b5998 !important; border: none !important; }
.divider { border-top: 1px solid #2a2a4a; margin: 10px 0; }
"""

with gr.Blocks(title="Street View Studio") as demo:
    gr.HTML("""
    <div class="dark-header">
      <h1>🗺️ Street View Studio</h1>
      <p>Fetch any location · Apply AI art styles or prototype building changes with FLUX.1-schnell (local)</p>
    </div>
    """)

    with gr.Row():
        # ── Fetch panel ──────────────────────────────────────────────────
        with gr.Column(scale=1):
            gr.HTML('<p class="section-label">1 · Fetch Street View</p>')
            address = gr.Textbox(
                label="Address or landmark",
                placeholder="1 Apple Park Way, Cupertino, CA",
                lines=1,
            )
            heading_auto = gr.Checkbox(label="Auto heading (default panorama angle)", value=True)
            with gr.Row():
                heading = gr.Slider(
                    label="Heading °", minimum=0, maximum=359, step=1, value=0,
                    info="0=N  90=E  180=S  270=W",
                )
                pitch = gr.Slider(
                    label="Pitch °", minimum=-30, maximum=30, step=1, value=0,
                    info="Tilt up/down",
                )
            fov = gr.Slider(
                label="Field of view °", minimum=20, maximum=120, step=5, value=90,
                info="Lower = more zoomed in",
            )
            fetch_btn = gr.Button("📷  Fetch Street View", variant="primary")

        # ── Street View result ───────────────────────────────────────────
        with gr.Column(scale=1):
            sv_image = gr.Image(label="Street View", type="pil", height=380, interactive=False)
            sv_info  = gr.Textbox(label="Location info", interactive=False, lines=2)

    gr.HTML('<div class="divider"></div>')

    with gr.Row():
        # ── Transform panel ──────────────────────────────────────────────
        with gr.Column(scale=1):
            gr.HTML('<p class="section-label">2 · AI Transform  (FLUX.1-schnell · local · Apache 2.0)</p>')
            preset = gr.Dropdown(
                label="Style / Edit preset",
                choices=PRESET_CHOICES,
                value="Watercolor painting",
            )
            active_prompt = gr.Textbox(
                label="Preset prompt (read-only)",
                value=STYLE_PRESETS["Watercolor painting"],
                lines=3,
                interactive=False,
            )
            custom_prompt = gr.Textbox(
                label="Custom addition  (appended to preset, or standalone with 'Custom')",
                placeholder="e.g. change the front door to bright red",
                lines=2,
            )
            with gr.Row():
                strength = gr.Slider(
                    label="Strength", minimum=0.1, maximum=0.99, step=0.05, value=0.90,
                    info="How much to change — lower preserves more of the original",
                )
                steps = gr.Slider(
                    label="Steps", minimum=4, maximum=20, step=1, value=8,
                )
            with gr.Row():
                seed      = gr.Number(label="Seed", value=42, precision=0)
                randomize = gr.Checkbox(label="Randomize seed", value=False)
            transform_btn = gr.Button("✨  Generate", variant="primary")

        # ── Output ───────────────────────────────────────────────────────
        with gr.Column(scale=1):
            out_image  = gr.Image(label="AI Output", type="pil", height=380, interactive=False)
            out_status = gr.Textbox(label="Status", interactive=False, lines=2)

    preset.change(
        fn=lambda p: STYLE_PRESETS.get(p, ""),
        inputs=[preset],
        outputs=[active_prompt],
    )

    fetch_btn.click(
        fetch_street_view,
        inputs=[address, heading_auto, heading, pitch, fov],
        outputs=[sv_image, sv_info],
    )

    transform_btn.click(
        transform_image,
        inputs=[sv_image, preset, custom_prompt, strength, steps, seed, randomize],
        outputs=[out_image, out_status],
    )

if __name__ == "__main__":
    demo.queue().launch(
        server_name="0.0.0.0",
        server_port=8040,
        css=CSS,
    )
