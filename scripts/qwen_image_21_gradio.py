#!/usr/bin/env python3
"""
Qwen-Image 2.1 Studio — Seed 13 Productions / Dragonsuite (port 8076)

Text-to-image, image editing with 1-10 reference images, and native transparent (RGBA)
output from Qwen/Qwen-Image-2.1 (40-step) or the official Qwen-Image-2.1-Turbo (8-step).

16GB card strategy (measured, see docs/venvs.md): the bf16 weights are a 14.2GB DiT plus a
17.5GB Qwen3-VL text encoder, more than the GPU holds and more than udragon's free RAM for
bf16 offload. scripts/quantize_qwen_image_21.py makes one-time NF4 (bitsandbytes 4-bit) copies
(~4.3GB DiT, ~6GB encoder). They load in seconds and run with model CPU offload, so only one
component sits on the GPU at a time. QI21_OFFLOAD=none keeps everything resident (faster, more VRAM).

Outputs: ~/ai_generated/qwen-image-21/  (timestamped RGBA-preserving PNGs; settings in the PNG
text chunk "parameters" and a .json sidecar).  License: Qwen Research License — non-commercial.
"""
import sys

sys.path.insert(0, "/srv/containers/edq/scripts")
import gpu_runtime  # noqa: E402  FIRST — configures the CUDA allocator before torch

import gc  # noqa: E402
import json  # noqa: E402
import logging  # noqa: E402
import os  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
from datetime import datetime  # noqa: E402
from logging.handlers import RotatingFileHandler  # noqa: E402
from pathlib import Path  # noqa: E402

import gradio as gr  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402
from PIL import Image, PngImagePlugin  # noqa: E402

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
PORT = int(os.environ.get("QI21_PORT", "8076"))
HOST = os.environ.get("QI21_HOST", "0.0.0.0")
MODEL_ROOT = Path(os.environ.get("QI21_MODEL_ROOT", "/srv/containers/edq/models/qwen-image-21"))
BASE_DIR = MODEL_ROOT / "Qwen-Image-2.1"
TURBO_DIR = MODEL_ROOT / "Qwen-Image-2.1-Turbo"
NF4_DIR = MODEL_ROOT / "nf4"
OUTPUT_DIR = Path(os.environ.get("QI21_OUTPUT_DIR", os.path.expanduser("~/ai_generated/qwen-image-21")))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = Path("/srv/containers/edq/logs/qwen_image_21.log")
FAVICON = "/srv/containers/edq/media/favicons/qwen-image-21.svg"
OFFLOAD = os.environ.get("QI21_OFFLOAD", "model")          # model | none
# Measured peak torch allocation is 6.4 GiB (t2i, any size) / 7.5 GiB (edit) with NF4 + offload.
MIN_FREE_VRAM_MIB = int(os.environ.get("QI21_MIN_FREE_VRAM_MIB", "8000"))

MODELS = {
    "Turbo (8 steps, fast)": "turbo",
    "Base (full quality, 40 steps)": "base",
}
DEFAULT_MODEL = "Turbo (8 steps, fast)"

# Official presets from the model card (all multiples of 32).
ASPECTS = {
    "1:1  · 2048×2048": (2048, 2048),
    "4:3  · 2400×1792": (2400, 1792),
    "3:4  · 1792×2400": (1792, 2400),
    "3:2  · 2528×1696": (2528, 1696),
    "2:3  · 1696×2528": (1696, 2528),
    "16:9 · 2752×1536": (2752, 1536),
    "9:16 · 1536×2752": (1536, 2752),
}
MATCH_INPUT = "Match reference image"
RGBA_PREFIX = "This is an RGBA image with transparency. "
RGBA_SUFFIX = " The image has alpha channel and the background is transparent."
LICENSE_NOTE = ("Model weights: **Qwen Research License** — non-commercial / research use only. "
                "Check the commercial-use terms (or get a license from Qwen) before any client work.")

# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #
log = logging.getLogger("qwen_image_21")
log.setLevel(logging.INFO)
_fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
_sh = logging.StreamHandler(sys.stdout)
_sh.setFormatter(_fmt)
log.addHandler(_sh)
try:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    _fh = RotatingFileHandler(LOG_FILE, maxBytes=2_000_000, backupCount=3)
    _fh.setFormatter(_fmt)
    log.addHandler(_fh)
except OSError:
    pass


# --------------------------------------------------------------------------- #
# Model management — one NF4 text encoder + VAE shared by both checkpoints;
# the 7B DiT is swapped when the user switches Base <-> Turbo.
# --------------------------------------------------------------------------- #
_lock = threading.Lock()
_state = {"pipe": None, "kind": None, "te": None, "vae": None, "status": "not loaded", "load_s": None}


def _free_vram_mib() -> int:
    free, _total = torch.cuda.mem_get_info()
    return int(free / 2**20)


def models_present() -> list[str]:
    missing = []
    for p in [BASE_DIR / "model_index.json", TURBO_DIR / "model_index.json",
              NF4_DIR / "text_encoder" / "config.json",
              NF4_DIR / "transformer-base" / "config.json", NF4_DIR / "transformer-turbo" / "config.json"]:
        if not p.exists():
            missing.append(str(p))
    return missing


def _release_pipe():
    pipe = _state["pipe"]
    if pipe is None:
        return
    try:
        pipe.remove_all_hooks()
    except Exception:
        pass
    old_tr = pipe.transformer
    _state["pipe"] = None
    del pipe, old_tr
    gc.collect()
    gpu_runtime.free_cuda_cache()


def load_pipeline(kind: str):
    """Return a ready pipeline for 'base' or 'turbo' (caller holds _lock)."""
    if _state["pipe"] is not None and _state["kind"] == kind:
        return _state["pipe"]
    from diffusers import AutoencoderKLQwenImage21, QwenImage21Pipeline, QwenImage21Transformer2DModel
    from transformers import Qwen3VLForConditionalGeneration

    missing = models_present()
    if missing:
        raise gr.Error("Model files missing — run scripts/download_qwen_image_21_models.sh then "
                       "scripts/quantize_qwen_image_21.py. Missing: " + ", ".join(missing))
    t0 = time.time()
    _state["status"] = f"loading {kind}…"
    log.info("loading %s pipeline (offload=%s, free VRAM %d MiB)", kind, OFFLOAD, _free_vram_mib())
    _release_pipe()
    if _state["te"] is None:
        _state["te"] = Qwen3VLForConditionalGeneration.from_pretrained(
            NF4_DIR / "text_encoder", dtype=torch.bfloat16, device_map={"": "cpu"})
    if _state["vae"] is None:
        _state["vae"] = AutoencoderKLQwenImage21.from_pretrained(BASE_DIR / "vae", dtype=torch.bfloat16)
    # Pre-quantized bnb weights cannot be device_map'd to CPU in diffusers; they load onto the GPU
    # and enable_model_cpu_offload() then parks them on the CPU between uses.
    transformer = QwenImage21Transformer2DModel.from_pretrained(
        NF4_DIR / f"transformer-{kind}", dtype=torch.bfloat16)
    src = TURBO_DIR if kind == "turbo" else BASE_DIR
    pipe = QwenImage21Pipeline.from_pretrained(
        src, text_encoder=_state["te"], vae=_state["vae"], transformer=transformer,
        dtype=torch.bfloat16, local_files_only=True)
    if OFFLOAD == "none":
        pipe.to("cuda")
    else:
        pipe.enable_model_cpu_offload()
    pipe.vae.enable_tiling()          # keeps 2K+ VAE decode inside the budget
    pipe.set_progress_bar_config(disable=True)
    _state.update(pipe=pipe, kind=kind, load_s=round(time.time() - t0, 1), status=f"{kind} ready")
    log.info("%s pipeline ready in %.1fs (free VRAM %d MiB)", kind, time.time() - t0, _free_vram_mib())
    return pipe


def warm_start():
    try:
        with _lock:
            load_pipeline(MODELS[DEFAULT_MODEL])
    except Exception as e:  # never kill the server over a warm start
        _state["status"] = f"warm start failed: {e}"
        log.exception("warm start failed")


# --------------------------------------------------------------------------- #
# Generation
# --------------------------------------------------------------------------- #
def _snap32(x: float) -> int:
    return max(256, int(round(x / 32.0)) * 32)


def resolve_size(aspect: str, preview: bool, refs: list[Image.Image]) -> tuple[int, int]:
    if aspect == MATCH_INPUT and refs:
        w0, h0 = refs[-1].size
        ratio = w0 / h0
        area = 2048 * 2048
    else:
        w0, h0 = ASPECTS.get(aspect, (2048, 2048))
        ratio = w0 / h0
        area = w0 * h0
    if preview:
        area = 1024 * 1024
    w = (area * ratio) ** 0.5
    h = w / ratio
    return _snap32(w), _snap32(h)


def _load_refs(files) -> list[Image.Image]:
    refs = []
    for f in files or []:
        path = f if isinstance(f, str) else getattr(f, "name", None) or f.get("path")
        im = Image.open(path)
        im.load()
        refs.append(im.convert("RGBA") if im.mode in ("RGBA", "LA", "P") else im.convert("RGB"))
    if len(refs) > 10:
        raise gr.Error("Qwen-Image 2.1 accepts up to 10 reference images.")
    return refs


def recent_gallery(limit: int = 24):
    files = sorted((p for p in OUTPUT_DIR.glob("qi21_*.png")), key=lambda p: p.stat().st_mtime, reverse=True)
    return [(str(p), p.stem.replace("qi21_", "")) for p in files[:limit]]


def _save(image: Image.Image, meta: dict, transparent: bool) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    mode = "edit" if meta["reference_images"] else "t2i"
    if image.mode == "RGBA" and not transparent:
        # The model always decodes 4 channels; ordinary images carry stray near-opaque alpha
        # (measured: min 181 on ~1% of pixels). Keep RGBA only when transparency was requested.
        image = image.convert("RGB")
    tag = "rgba" if image.mode == "RGBA" else mode
    path = OUTPUT_DIR / f"qi21_{stamp}_{meta['model']}_{tag}_{meta['seed']}.png"
    n = 1
    while path.exists():
        path = path.with_name(path.stem + f"_{n}.png")
        n += 1
    info = PngImagePlugin.PngInfo()
    info.add_text("parameters", json.dumps(meta, ensure_ascii=False))
    info.add_text("Software", "Qwen-Image 2.1 Studio — Seed 13 Productions / Dragonsuite")
    image.save(path, pnginfo=info)
    path.with_suffix(".json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    try:
        image.save(OUTPUT_DIR / "latest.png")
    except OSError:
        pass
    meta["mode_saved"] = image.mode
    return path


def generate(prompt, model_label, ref_files, transparent, aspect, preview, steps, seed, randomize,
             cfg, negative, progress=gr.Progress()):
    prompt = (prompt or "").strip()
    if not prompt:
        raise gr.Error("Write a prompt first.")
    kind = MODELS.get(model_label, "turbo")
    refs = _load_refs(ref_files)
    if randomize or seed is None or int(seed) < 0:
        seed = int(np.random.randint(0, 2**31 - 1))
    seed = int(seed)
    width, height = resolve_size(aspect, bool(preview), refs)
    full_prompt = prompt
    if transparent and not prompt.lower().startswith("this is an rgba image"):
        full_prompt = RGBA_PREFIX + prompt.rstrip(". ") + "." + RGBA_SUFFIX
    steps = int(steps)

    with _lock:  # one generation at a time on the single GPU
        gpu_runtime.free_cuda_cache()
        # usable = what the driver has free + what this process already holds in its cache
        free = _free_vram_mib() + int(torch.cuda.memory_reserved() / 2**20)
        if free < MIN_FREE_VRAM_MIB:
            log.warning("refused: only %d MiB VRAM usable (need %d)", free, MIN_FREE_VRAM_MIB)
            raise gr.Error(f"Only {free} MiB VRAM free (need ~{MIN_FREE_VRAM_MIB}). Another GPU tool "
                           "(e.g. Gemma/Ollama, Krea2) is using the card — stop it from the Dashboard and retry. "
                           "Nothing was unloaded.")
        progress(0.02, desc=f"Loading {kind} model…")
        pipe = load_pipeline(kind)
        total = 8 if kind == "turbo" else steps

        def _cb(_pipe, i, _t, kw):
            progress((i + 1) / total, desc=f"Step {i + 1}/{total}")
            return kw

        kwargs = dict(prompt=full_prompt, width=width, height=height, use_kv_cache=True,
                      generator=torch.Generator("cpu").manual_seed(seed), callback_on_step_end=_cb)
        if kind == "base":
            kwargs["num_inference_steps"] = steps
            if cfg and float(cfg) > 1 and (negative or "").strip():
                kwargs["true_cfg_scale"] = float(cfg)
                kwargs["negative_prompt"] = negative.strip()
        if refs:
            kwargs["image"] = refs
            kwargs["output_resolution"] = int(round((width * height) ** 0.5))
        torch.cuda.reset_peak_memory_stats()
        t0 = time.time()
        try:
            with gpu_runtime.oom_guard("Qwen-Image 2.1 generation"):
                image = pipe(**kwargs).images[0]
        except RuntimeError as e:
            log.error("generation failed: %s", e)
            raise gr.Error(str(e))
        finally:
            gpu_runtime.free_cuda_cache()   # hand idle VRAM back to other tools (Gemma etc.)
        elapsed = time.time() - t0
        peak = torch.cuda.max_memory_allocated() / 2**30

    meta = {
        "prompt": prompt, "full_prompt": full_prompt, "model": kind,
        "model_repo": "Qwen/Qwen-Image-2.1-Turbo" if kind == "turbo" else "Qwen/Qwen-Image-2.1",
        "quantization": "bitsandbytes NF4 (transformer + text encoder language model)",
        "width": image.width, "height": image.height, "steps": 8 if kind == "turbo" else steps,
        "seed": seed, "true_cfg_scale": kwargs.get("true_cfg_scale", 1.0),
        "negative_prompt": kwargs.get("negative_prompt"), "transparent_requested": bool(transparent),
        "reference_images": len(refs), "aspect": aspect, "fast_preview": bool(preview),
        "seconds": round(elapsed, 1), "peak_vram_gib_torch": round(peak, 2),
        "created": datetime.now().isoformat(timespec="seconds"),
        "license": "Qwen Research License (non-commercial)",
    }
    path = _save(image, meta, bool(transparent))
    log.info("saved %s (%dx%d %s) in %.1fs, peak torch VRAM %.2f GiB", path.name, image.width,
             image.height, meta["mode_saved"], elapsed, peak)
    status = (f"✅ **{kind}** · {image.width}×{image.height} · {meta['mode_saved']} · seed `{seed}` · "
              f"{elapsed:.1f}s · peak VRAM {peak:.1f} GiB  \nSaved: `{path}`")
    return str(path), recent_gallery(), status, seed


def ui_status():
    try:
        free = _free_vram_mib()
    except Exception:
        free = -1
    return f"Model: **{_state['status']}** · free VRAM {free} MiB · offload: {OFFLOAD}"


def use_as_reference(path, current):
    if not path:
        return current
    files = [f if isinstance(f, str) else getattr(f, "name", f) for f in (current or [])]
    return files + [path]


# --------------------------------------------------------------------------- #
# UI — Seed 13 Productions purple/gold, dark by default (localStorage toggle)
# --------------------------------------------------------------------------- #
CSS = """
:root { --s13-purple: #7c3aed; --s13-purple-deep: #4c1d95; --s13-gold: #d8af62; --s13-gold-soft: #e9cf94; }
.gradio-container { max-width: 1500px !important; transition: background-color .3s ease, color .3s ease; }
body.dark, body.dark .gradio-container { background: linear-gradient(160deg, #1a1a2e 0%, #1e1e1e 55%, #241a33 100%) !important; }
#s13-header { display:flex; align-items:center; justify-content:space-between; gap:12px;
  padding:14px 18px; border-radius:14px; border:1px solid var(--s13-gold);
  background: linear-gradient(135deg, var(--s13-purple-deep) 0%, var(--s13-purple) 60%, #9b6b2f 100%); }
#s13-header h1 { margin:0; color:#fff; font-size:1.55rem; letter-spacing:.3px; }
#s13-header .kicker { color: var(--s13-gold-soft); font-size:.78rem; letter-spacing:2px; text-transform:uppercase; margin:0 0 2px; }
#s13-header .sub { color:#ede9fe; font-size:.9rem; margin:2px 0 0; }
#theme-toggle { width:44px !important; min-width:44px !important; height:44px; border-radius:50% !important;
  border:1px solid var(--s13-gold) !important; background: rgba(0,0,0,.25) !important; color:#fff !important;
  font-size:1.2rem; transition: transform .3s ease; flex: 0 0 44px !important; }
#theme-toggle:hover { transform: rotate(180deg); }
#license-note { border-left:3px solid var(--s13-gold); padding:6px 10px; border-radius:6px; font-size:.85rem; }
body.dark #license-note { background:#2d2d2d; color:#e0e0e0; }
#go-btn { background: linear-gradient(135deg, var(--s13-purple) 0%, var(--s13-purple-deep) 100%) !important;
  border:1px solid var(--s13-gold) !important; color:#fff !important; font-weight:600; }
#go-btn:hover { filter: brightness(1.12); }
.checker img { background-color:#ddd; background-image:
  linear-gradient(45deg,#bbb 25%,transparent 25%), linear-gradient(-45deg,#bbb 25%,transparent 25%),
  linear-gradient(45deg,transparent 75%,#bbb 75%), linear-gradient(-45deg,transparent 75%,#bbb 75%);
  background-size:20px 20px; background-position:0 0,0 10px,10px -10px,-10px 0; }
#s13-footer { text-align:center; color:#9ca3af; font-size:.8rem; padding-top:6px; }
#s13-footer b { color: var(--s13-gold); }
footer { display:none !important; }
"""

THEME_JS = """
() => {
  const pref = localStorage.getItem('qwen-image-21-theme');
  const dark = pref !== 'light';
  document.body.classList.toggle('dark', dark);
  if (!pref) localStorage.setItem('qwen-image-21-theme', 'dark');
  const b = document.querySelector('#theme-toggle'); if (b) b.textContent = dark ? '☀️' : '🌙';
}
"""
TOGGLE_JS = """
() => {
  const dark = !document.body.classList.contains('dark');
  document.body.classList.toggle('dark', dark);
  localStorage.setItem('qwen-image-21-theme', dark ? 'dark' : 'light');
  const b = document.querySelector('#theme-toggle'); if (b) b.textContent = dark ? '☀️' : '🌙';
}
"""

THEME = gr.themes.Soft(primary_hue="violet", secondary_hue="amber", neutral_hue="slate").set(
    body_background_fill_dark="#1e1e1e", block_background_fill_dark="#2d2d2d",
    border_color_primary_dark="#4a5568", body_text_color_dark="#e0e0e0",
    input_background_fill_dark="#2d2d2d", button_secondary_background_fill_dark="#374151",
)

with gr.Blocks(title="Qwen-Image 2.1 Studio — Seed 13") as demo:
    with gr.Row(elem_id="s13-header"):
        gr.HTML("<div><p class='kicker'>Seed 13 Productions · Dragonsuite</p>"
                "<h1>🐉 Qwen-Image 2.1 Studio</h1>"
                "<p class='sub'>Text-to-image · multi-reference editing · native transparent PNGs</p></div>")
        theme_btn = gr.Button("☀️", elem_id="theme-toggle", scale=0, min_width=44)
    gr.Markdown(LICENSE_NOTE, elem_id="license-note")
    with gr.Row():
        with gr.Column(scale=5):
            prompt = gr.Textbox(label="Prompt", lines=4,
                                placeholder="A copper dragon perched on a lighthouse at dusk, cinematic light…")
            with gr.Row():
                model = gr.Radio(list(MODELS), value=DEFAULT_MODEL, label="Model")
                transparent = gr.Checkbox(value=False, label="Transparent background (RGBA)")
            refs = gr.File(label="Reference images for editing (optional, 1-10)", file_count="multiple",
                           file_types=["image"], type="filepath")
            with gr.Row():
                aspect = gr.Dropdown(list(ASPECTS) + [MATCH_INPUT], value=list(ASPECTS)[0], label="Aspect ratio")
                preview = gr.Checkbox(value=True, label="Fast preview (~1 MP instead of ~4 MP)")
            with gr.Accordion("Advanced", open=False):
                steps = gr.Slider(8, 60, value=40, step=1, label="Steps (Base model; Turbo always uses its 8-step schedule)")
                with gr.Row():
                    seed = gr.Number(value=-1, precision=0, label="Seed (-1 = random)")
                    randomize = gr.Checkbox(value=True, label="Randomize seed")
                cfg = gr.Slider(1.0, 8.0, value=1.0, step=0.5,
                                label="CFG (Base only; >1 needs a negative prompt; model is tuned for 1.0)")
                negative = gr.Textbox(label="Negative prompt (Base, CFG > 1)", lines=1)
            go = gr.Button("Generate", variant="primary", elem_id="go-btn")
            status = gr.Markdown(ui_status())
        with gr.Column(scale=6):
            result = gr.Image(label="Result", type="filepath", image_mode="RGBA", format="png",
                              elem_classes=["checker"], height=640, interactive=False)
            reuse = gr.Button("↪ Use result as a reference image", size="sm")
            gallery = gr.Gallery(label=f"Recent outputs — {OUTPUT_DIR}", value=recent_gallery, columns=6,
                                 height=300, object_fit="contain", elem_classes=["checker"])
    gr.HTML("<div id='s13-footer'>Built with Qwen · <b>Seed 13 Productions</b> · outputs in "
            f"<code>{OUTPUT_DIR}</code></div>")

    theme_btn.click(fn=None, js=TOGGLE_JS)
    go.click(generate, [prompt, model, refs, transparent, aspect, preview, steps, seed, randomize, cfg, negative],
             [result, gallery, status, seed], api_name="generate", concurrency_limit=1)
    reuse.click(use_as_reference, [result, refs], refs, api_name=False)
    demo.load(ui_status, None, status, api_name=False)
    status_timer = gr.Timer(10)
    status_timer.tick(ui_status, None, status, api_name=False)


if __name__ == "__main__":
    log.info("Qwen-Image 2.1 Studio starting on %s:%d — outputs %s", HOST, PORT, OUTPUT_DIR)
    if not torch.cuda.is_available():
        log.error("CUDA not available — refusing to start")
        sys.exit(1)
    threading.Thread(target=warm_start, daemon=True).start()
    demo.queue(max_size=8, default_concurrency_limit=1)
    demo.launch(server_name=HOST, server_port=PORT, share=False, show_error=True,
                favicon_path=FAVICON if Path(FAVICON).exists() else None,
                allowed_paths=[str(OUTPUT_DIR)], theme=THEME, css=CSS, js=THEME_JS)
