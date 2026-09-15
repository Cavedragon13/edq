#!/usr/bin/env python3
"""
Marigold V2 — depth / surface normals / albedo from a single image
(Huawei Bayer Lab, SIGGRAPH Asia 2026). One deterministic step on a
Qwen-Image-Edit-2509 backbone with a per-modality LoRA + fine-tuned VAE decoder.

This is a thin Gradio front-end over the local ComfyUI (port 8188): the
official code needs ~17 GB VRAM at 1024², which does not fit the 16 GB card, so
the backbone runs as a Q4_K_S GGUF through ComfyUI-GGUF + the ComfyUI-Marigold-v2
node pack. ComfyUI owns the GPU; this process holds no model.

Outputs: ~/ai_generated/marigold-v2/  (timestamped PNGs; depth also gets a
Spectral colorized render and optional float32 .npy).  Dragonsuite port 8066.
"""

import json
import os
import shutil
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

import gradio as gr
import requests

PORT = 8066
COMFY = os.environ.get("COMFY_URL", "http://127.0.0.1:8188")
COMFY_OUTPUT = Path("/srv/containers/edq/projects/ComfyUI/output")
OUTPUT_DIR = Path(os.path.expanduser("~/ai_generated/marigold-v2"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
FAVICON = "/srv/containers/edq/media/favicons/marigold-v2.svg"

GGUF = "Qwen-Image-Edit-2509-Q4_K_S.gguf"
BASE_VAE = "qwen_image_vae.safetensors"
LORA = {
    "depth": "marigold-v2-depth-Log-stage2.safetensors",
    "normals": "marigold-v2-normals.safetensors",
    "albedo": "marigold-v2-albedo.safetensors",
}
COLORMAPS = ["Spectral_r", "Spectral", "viridis", "magma", "inferno", "turbo", "gray"]


# --------------------------------------------------------------------------- #
# ComfyUI API helpers (HTTP only — no model in this process)
# --------------------------------------------------------------------------- #
def comfy_up() -> bool:
    try:
        return requests.get(f"{COMFY}/system_stats", timeout=3).ok
    except requests.RequestException:
        return False


def upload_image(path: str) -> str:
    with open(path, "rb") as f:
        r = requests.post(f"{COMFY}/upload/image",
                          files={"image": (os.path.basename(path), f)},
                          data={"overwrite": "true"}, timeout=60)
    r.raise_for_status()
    return r.json()["name"]


def build_workflow(image_name: str, modality: str, max_side: int, colormap: str,
                   near_is_bright: bool, save_raw: bool, vae_tiling: bool, seed: int) -> dict:
    prefix = f"marigold_v2/{modality}"
    wf = {
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": GGUF}},
        "2": {"class_type": "VAELoader", "inputs": {"vae_name": BASE_VAE}},
        "3": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "4": {"class_type": "MarigoldV2LoRALoader", "inputs": {
            "model": ["1", 0], "vae": ["2", 0], "lora_name": LORA[modality],
            "modality": modality, "depth_parameterization": "log_or_linear",
            "strength": 1.0, "auto_download": False}},
        "5": {"class_type": "MarigoldV2Predict", "inputs": {
            "marigold_model": ["4", 0], "image": ["3", 0], "vae": ["4", 2],
            "resolution_mode": "max_side", "max_side": int(max_side),
            "width": 1024, "height": 1024, "encoder_seed": int(seed),
            "keep_input_size": True, "near_is_bright": bool(near_is_bright),
            "vae_tiling": bool(vae_tiling), "keep_model_loaded": True}},
        "6": {"class_type": "SaveImage", "inputs": {"images": ["5", 0], "filename_prefix": prefix}},
    }
    if modality == "depth":
        wf["7"] = {"class_type": "MarigoldV2ColorizeDepth", "inputs": {
            "raw": ["5", 1], "colormap": colormap, "near_is_bright": bool(near_is_bright),
            "percentile_clip": 0.0}}
        wf["8"] = {"class_type": "SaveImage", "inputs": {"images": ["7", 0],
                                                          "filename_prefix": prefix + "_color"}}
    if save_raw:
        wf["9"] = {"class_type": "MarigoldV2SaveRaw", "inputs": {"raw": ["5", 1],
                                                                  "filename_prefix": prefix + "_raw"}}
    return wf


def run_workflow(wf: dict, timeout_s: int = 900) -> dict:
    r = requests.post(f"{COMFY}/prompt", json={"prompt": wf}, timeout=60)
    if not r.ok:
        try:
            detail = r.json()
        except ValueError:
            detail = r.text
        raise gr.Error(f"ComfyUI rejected the workflow: {detail}")
    pid = r.json()["prompt_id"]
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        h = requests.get(f"{COMFY}/history/{pid}", timeout=30).json()
        if pid in h:
            entry = h[pid]
            status = entry.get("status", {})
            if status.get("status_str") == "error":
                msgs = [m[1].get("exception_message", "") for m in status.get("messages", [])
                        if m[0] == "execution_error"]
                raise gr.Error("ComfyUI execution error: " + ("; ".join(msgs) or "see ComfyUI log"))
            return entry
        time.sleep(1.5)
    raise gr.Error("Timed out waiting for ComfyUI (first run loads a 12 GB backbone; try again).")


def collect_outputs(entry: dict, modality: str, stamp: str) -> list[Path]:
    saved = []
    for node_id, out in entry.get("outputs", {}).items():
        for img in out.get("images", []):
            src = COMFY_OUTPUT / img.get("subfolder", "") / img["filename"]
            if not src.exists():
                continue
            tag = "color" if node_id == "8" else modality
            dest = OUTPUT_DIR / f"marigold_v2_{tag}_{stamp}{src.suffix}"
            shutil.copy2(src, dest)
            saved.append(dest)
    # .npy from the raw saver lands in ComfyUI/output/<prefix>_raw*.npy
    raw_dir = COMFY_OUTPUT / "marigold_v2"
    if raw_dir.exists():
        for npy in sorted(raw_dir.glob(f"{modality}_raw*.npy"), key=os.path.getmtime)[-1:]:
            if time.time() - npy.stat().st_mtime < 120:
                dest = OUTPUT_DIR / f"marigold_v2_{modality}_raw_{stamp}.npy"
                shutil.copy2(npy, dest)
                saved.append(dest)
    return saved


def predict(image_path, modality, max_side, colormap, near_is_bright, save_raw, vae_tiling, seed):
    if not image_path:
        raise gr.Error("Upload an image first.")
    if not comfy_up():
        raise gr.Error("ComfyUI (port 8188) is not running — start Marigold V2 from the Dashboard, "
                       "which launches ComfyUI first.")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = upload_image(image_path)
    wf = build_workflow(name, modality, max_side, colormap, near_is_bright, save_raw, vae_tiling, seed)
    t0 = time.time()
    entry = run_workflow(wf)
    saved = collect_outputs(entry, modality, stamp)
    if not saved:
        raise gr.Error("ComfyUI finished but produced no images — check /tmp/comfyui.log")
    pngs = [p for p in saved if p.suffix == ".png"]
    primary = next((p for p in pngs if "_color_" not in p.name), pngs[0])
    color = next((p for p in pngs if "_color_" in p.name), None)
    shutil.copy2(primary, OUTPUT_DIR / f"latest_{modality}.png")
    msg = f"{modality} in {time.time() - t0:.1f}s → " + ", ".join(p.name for p in saved)
    print("  " + msg)
    return str(primary), (str(color) if color else None), [str(p) for p in saved], msg


DARK_JS = """
() => {
  const pref = localStorage.getItem('marigold-theme') || 'dark';
  document.body.classList.toggle('dark', pref === 'dark');
}
"""
TOGGLE_JS = """
() => {
  const dark = !document.body.classList.contains('dark');
  document.body.classList.toggle('dark', dark);
  localStorage.setItem('marigold-theme', dark ? 'dark' : 'light');
}
"""

with gr.Blocks(title="Marigold V2", js=DARK_JS,
               theme=gr.themes.Soft(primary_hue="orange", secondary_hue="green")) as demo:
    with gr.Row():
        gr.Markdown(
            "# 🌼 Marigold V2 — depth · normals · albedo\n"
            "Single-step dense prediction on a Qwen-Image-Edit-2509 backbone (Q4_K_S GGUF via ComfyUI). "
            "Outputs: `~/ai_generated/marigold-v2/`"
        )
        theme_btn = gr.Button("🌙 / ☀️", scale=0, min_width=80)
    theme_btn.click(fn=None, js=TOGGLE_JS)
    with gr.Row():
        with gr.Column():
            image = gr.Image(label="Input image", type="filepath")
            modality = gr.Radio(["depth", "normals", "albedo"], value="depth", label="Modality")
            max_side = gr.Slider(512, 1536, value=1024, step=64,
                                 label="Max side (px) — 1024 is the tested budget on 16 GB")
            with gr.Row():
                colormap = gr.Dropdown(COLORMAPS, value="Spectral_r", label="Depth colormap")
                near_is_bright = gr.Checkbox(value=True, label="Near = bright")
            with gr.Row():
                save_raw = gr.Checkbox(value=False, label="Also save float32 .npy")
                vae_tiling = gr.Checkbox(value=False, label="VAE tiling (large inputs)")
            seed = gr.Number(value=2025, precision=0, label="Encoder seed (minor effect)")
            go = gr.Button("Predict", variant="primary")
        with gr.Column():
            out_primary = gr.Image(label="Prediction (grayscale depth / normals / albedo)")
            out_color = gr.Image(label="Colorized depth")
            files = gr.File(label="Saved files", file_count="multiple")
            status = gr.Markdown()
    go.click(predict, [image, modality, max_side, colormap, near_is_bright, save_raw, vae_tiling, seed],
             [out_primary, out_color, files, status])

if __name__ == "__main__":
    print("Marigold V2 front-end")
    print("=====================")
    print(f"ComfyUI: {COMFY}   Output: {OUTPUT_DIR}")
    demo.queue(max_size=4, default_concurrency_limit=1)
    demo.launch(server_name="0.0.0.0", server_port=PORT, share=False, show_error=True,
                favicon_path=FAVICON if Path(FAVICON).exists() else None,
                allowed_paths=[str(OUTPUT_DIR)])
