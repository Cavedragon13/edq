#!/usr/bin/env python3
"""Ideogram 4 Gradio service for Dragonsuite."""

from __future__ import annotations

import gc
import json
import os
import time
from datetime import datetime
from pathlib import Path

import gradio as gr
import torch

from ideogram4 import (
    DEFAULT_MAGIC_PROMPT,
    MAGIC_PROMPTS,
    PRESETS,
    Ideogram4Pipeline,
    Ideogram4PipelineConfig,
    aspect_ratio_from_size,
    moderate_image,
    moderate_prompt,
)


ROOT = Path("/srv/containers/edq")
OUTPUT_DIR = Path(os.path.expanduser("~/ai_generated/ideogram4"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

QUANTIZATION_REPOS = {
    "nf4": "ideogram-ai/ideogram-4-nf4",
    "fp8": "ideogram-ai/ideogram-4-fp8",
}

ASPECT_RATIOS = {
    "Square 1:1 (1024x1024)": (1024, 1024),
    "Landscape 3:2 (1536x1024)": (1536, 1024),
    "Portrait 2:3 (1024x1536)": (1024, 1536),
    "Widescreen 16:9 (1920x1088)": (1920, 1088),
    "Phone 9:16 (1024x1792)": (1024, 1792),
    "Banner 4:1 (1600x400)": (1600, 400),
    "Small smoke test (512x512)": (512, 512),
    "Custom": None,
}

PROMPT_MODES = [
    "Magic prompt via Ideogram API",
    "Plain prompt direct",
    "Structured JSON direct",
]

pipe: Ideogram4Pipeline | None = None
loaded_quantization: str | None = None


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


load_env_file(ROOT / ".env")
load_env_file(Path(__file__).resolve().parent / ".env")
os.environ.setdefault("HF_HOME", str(ROOT / "cache_huggingface"))
os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(Path(os.environ["HF_HOME"]) / "hub"))


def normalize_dimension(value: int | float, name: str) -> int:
    dim = int(value)
    if dim < 256 or dim > 2048:
        raise gr.Error(f"{name} must be between 256 and 2048.")
    if dim % 16 != 0:
        raise gr.Error(f"{name} must be a multiple of 16.")
    return dim


def dimensions_for(aspect_ratio: str, custom_width: int | float, custom_height: int | float) -> tuple[int, int]:
    preset = ASPECT_RATIOS[aspect_ratio]
    if preset is not None:
        return preset
    width = normalize_dimension(custom_width, "Width")
    height = normalize_dimension(custom_height, "Height")
    if max(width / height, height / width) > 6:
        raise gr.Error("Aspect ratio must be no wider than 6:1 or 1:6.")
    return width, height


def get_pipeline(quantization: str) -> Ideogram4Pipeline:
    global pipe, loaded_quantization

    if pipe is not None and loaded_quantization == quantization:
        return pipe

    if quantization == "nf4" and not torch.cuda.is_available():
        raise gr.Error("nf4 requires CUDA. Use fp8 on non-CUDA hardware.")

    if pipe is not None:
        del pipe
        pipe = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    # Transformers 5.10 preallocates a large CUDA warmup buffer while loading
    # the quantized Qwen3-VL text encoder. On a 16GB card, the real model fits
    # but that extra warmup reservation does not.
    try:
        import transformers.modeling_utils as modeling_utils

        modeling_utils.caching_allocator_warmup = lambda *args, **kwargs: None
    except Exception:
        pass

    device = "cuda" if torch.cuda.is_available() else "cpu"
    pipe = Ideogram4Pipeline.from_pretrained(
        config=Ideogram4PipelineConfig(weights_repo=QUANTIZATION_REPOS[quantization]),
        device=device,
        dtype=torch.bfloat16,
    )
    loaded_quantization = quantization
    return pipe


def prepare_prompt(
    prompt: str,
    prompt_mode: str,
    width: int,
    height: int,
    magic_prompt_model: str,
    warn_on_caption_issues: bool,
) -> tuple[str, bool]:
    prompt = prompt.strip()
    if not prompt:
        raise gr.Error("Enter a prompt first.")

    if prompt_mode == "Structured JSON direct":
        try:
            json.loads(prompt)
        except json.JSONDecodeError as exc:
            raise gr.Error(f"Structured JSON prompt is not valid JSON: {exc}") from exc
        return prompt, warn_on_caption_issues

    if prompt_mode == "Plain prompt direct":
        return prompt, False

    api_key = os.environ.get("MAGIC_PROMPT_API_KEY") or os.environ.get("IDEOGRAM_API_KEY")
    if not api_key:
        raise gr.Error("Magic prompt needs IDEOGRAM_API_KEY or MAGIC_PROMPT_API_KEY in /srv/containers/edq/.env.")
    aspect_ratio = aspect_ratio_from_size(width, height)
    magic = MAGIC_PROMPTS[magic_prompt_model](api_key=api_key)
    return magic.expand(prompt, aspect_ratio=aspect_ratio), warn_on_caption_issues


def run_safety_prompt(prompt: str, enabled: bool) -> str:
    key = os.environ.get("HIVE_TEXT_MODERATION_KEY")
    if not enabled or not key:
        return "Prompt safety: skipped"
    flags = moderate_prompt(prompt, key)
    if flags:
        details = ", ".join(f"{name}={score:.3f}" for name, score in flags)
        raise gr.Error(f"Hive text moderation rejected the prompt: {details}")
    return "Prompt safety: passed"


def run_safety_image(image, enabled: bool) -> str:
    key = os.environ.get("HIVE_VISUAL_MODERATION_KEY")
    if not enabled or not key:
        return "Image safety: skipped"
    flags = moderate_image(image, key)
    if flags:
        details = ", ".join(f"{name}={score:.3f}" for name, score in flags)
        raise gr.Error(f"Hive visual moderation rejected the image: {details}")
    return "Image safety: passed"


def save_artifacts(image, caption: str, original_prompt: str, metadata: dict) -> tuple[str, str]:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in original_prompt[:48]).strip("-")
    slug = slug or "ideogram4"
    image_path = OUTPUT_DIR / f"{stamp}-{slug}.png"
    meta_path = OUTPUT_DIR / f"{stamp}-{slug}.json"
    image.save(image_path)
    meta_path.write_text(
        json.dumps(
            {
                "original_prompt": original_prompt,
                "caption": caption,
                **metadata,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return str(image_path), str(meta_path)


def generate(
    prompt: str,
    prompt_mode: str,
    aspect_ratio: str,
    custom_width: int,
    custom_height: int,
    sampler_preset: str,
    seed: int,
    quantization: str,
    magic_prompt_model: str,
    warn_on_caption_issues: bool,
    hive_safety: bool,
):
    width, height = dimensions_for(aspect_ratio, custom_width, custom_height)
    safety_prompt = run_safety_prompt(prompt, hive_safety)
    caption, raise_on_caption_issues = prepare_prompt(
        prompt,
        prompt_mode,
        width,
        height,
        magic_prompt_model,
        warn_on_caption_issues,
    )

    preset = PRESETS[sampler_preset]
    model = get_pipeline(quantization)
    start = time.monotonic()
    images = model(
        caption,
        height=height,
        width=width,
        num_steps=preset.num_steps,
        guidance_schedule=preset.guidance_schedule,
        mu=preset.mu,
        std=preset.std,
        seed=int(seed) if int(seed) >= 0 else None,
        raise_on_caption_issues=raise_on_caption_issues,
    )
    elapsed = time.monotonic() - start
    image = images[0]
    safety_image = run_safety_image(image, hive_safety)
    image_path, meta_path = save_artifacts(
        image,
        caption,
        prompt,
        {
            "width": width,
            "height": height,
            "sampler_preset": sampler_preset,
            "seed": int(seed),
            "quantization": quantization,
            "prompt_mode": prompt_mode,
            "magic_prompt_model": magic_prompt_model if "Magic" in prompt_mode else None,
            "elapsed_seconds": round(elapsed, 2),
            "safety": [safety_prompt, safety_image],
        },
    )
    status = (
        f"Saved {image_path}\n"
        f"Metadata {meta_path}\n"
        f"{width}x{height}, {sampler_preset}, seed {seed}, {elapsed:.1f}s\n"
        f"{safety_prompt}; {safety_image}"
    )
    return image_path, image_path, caption, status


CSS = """
.gradio-container { max-width: 1440px !important; }
#caption textarea { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }
"""


def build_app() -> gr.Blocks:
    with gr.Blocks(title="Ideogram 4") as demo:
        gr.Markdown("# Ideogram 4")
        with gr.Row():
            with gr.Column(scale=5):
                prompt = gr.Textbox(
                    label="Prompt",
                    lines=7,
                    value='A crisp product poster for a fictional synth called "DRAGONWAVE", with the exact title text DRAGONWAVE in glossy chrome letters.',
                )
                with gr.Row():
                    prompt_mode = gr.Dropdown(PROMPT_MODES, value=PROMPT_MODES[0], label="Prompt mode")
                    sampler = gr.Dropdown(sorted(PRESETS.keys()), value="V4_TURBO_12", label="Sampler")
                with gr.Row():
                    aspect = gr.Dropdown(list(ASPECT_RATIOS), value="Square 1:1 (1024x1024)", label="Size")
                    seed = gr.Number(value=42, precision=0, label="Seed (-1 random)")
                with gr.Row():
                    width = gr.Number(value=1024, precision=0, label="Custom width")
                    height = gr.Number(value=1024, precision=0, label="Custom height")
                with gr.Row():
                    quantization = gr.Dropdown(["nf4", "fp8"], value="nf4", label="Quantization")
                    magic_model = gr.Dropdown(sorted(MAGIC_PROMPTS), value=DEFAULT_MAGIC_PROMPT, label="Magic model")
                with gr.Row():
                    warn = gr.Checkbox(value=True, label="Warn on caption issues")
                    hive = gr.Checkbox(value=bool(os.environ.get("HIVE_TEXT_MODERATION_KEY") and os.environ.get("HIVE_VISUAL_MODERATION_KEY")), label="Hive safety")
                run = gr.Button("Generate", variant="primary")
            with gr.Column(scale=6):
                image = gr.Image(label="Output", type="filepath", height=720)
                file_out = gr.File(label="Download")
        caption = gr.Textbox(label="Caption sent to model", lines=10, elem_id="caption")
        status = gr.Textbox(label="Status", lines=5)

        run.click(
            fn=generate,
            inputs=[
                prompt,
                prompt_mode,
                aspect,
                width,
                height,
                sampler,
                seed,
                quantization,
                magic_model,
                warn,
                hive,
            ],
            outputs=[image, file_out, caption, status],
            api_name="generate",
            concurrency_limit=1,
        )
    return demo


if __name__ == "__main__":
    port = int(os.environ.get("IDEOGRAM4_PORT", "8054"))
    app = build_app()
    app.queue(max_size=4).launch(
        server_name="0.0.0.0",
        server_port=port,
        css=CSS,
        footer_links=[],
        show_error=True,
    )
