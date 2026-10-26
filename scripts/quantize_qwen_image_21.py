#!/usr/bin/env python3
"""One-time NF4 (bitsandbytes 4-bit) quantization for Qwen-Image 2.1 Studio (Dragonsuite 8076).

Why: the official bf16 weights are a 14.2GB DiT + 17.5GB Qwen3-VL text encoder. They do not fit the
16GB RTX 5070 Ti together, and udragon only has ~14GB of free RAM for CPU offload, so bf16 offload
swaps. NF4 copies are ~4GB (transformer) and ~5.5GB (text encoder) and load in seconds.

Writes (idempotent; skips parts that already exist):
  models/qwen-image-21/nf4/text_encoder        Qwen3-VL text encoder, language model NF4, vision tower bf16
  models/qwen-image-21/nf4/transformer-base    Qwen-Image-2.1 DiT, NF4
  models/qwen-image-21/nf4/transformer-turbo   Qwen-Image-2.1-Turbo DiT, NF4

Needs ~8GB free VRAM while it runs. Usage:
  venv_qwen_image_21/bin/python scripts/quantize_qwen_image_21.py [--only text_encoder|base|turbo]
"""
import argparse
import gc
import sys
import time
from pathlib import Path

sys.path.insert(0, "/srv/containers/edq/scripts")
import gpu_runtime  # noqa: E402,F401  (configures the CUDA allocator before torch)
import torch  # noqa: E402

ROOT = Path("/srv/containers/edq/models/qwen-image-21")
BASE = ROOT / "Qwen-Image-2.1"
TURBO = ROOT / "Qwen-Image-2.1-Turbo"
NF4 = ROOT / "nf4"


def _done(path: Path) -> bool:
    return (path / "config.json").exists() and any(path.glob("*.safetensors"))


def quantize_text_encoder():
    out = NF4 / "text_encoder"
    if _done(out):
        print(f"[skip] {out} exists", flush=True)
        return
    from transformers import BitsAndBytesConfig, Qwen3VLForConditionalGeneration
    cfg = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=False,
        llm_int8_skip_modules=["visual", "lm_head"],   # keep the small vision tower + head in bf16
    )
    t0 = time.time()
    print("Quantizing text encoder (Qwen3-VL 8B) to NF4 ...", flush=True)
    te = Qwen3VLForConditionalGeneration.from_pretrained(
        BASE / "text_encoder", quantization_config=cfg, dtype=torch.bfloat16, device_map={"": 0})
    out.mkdir(parents=True, exist_ok=True)
    te.save_pretrained(out, safe_serialization=True)
    print(f"  saved {out} in {time.time() - t0:.0f}s, peak VRAM {torch.cuda.max_memory_allocated() / 2**30:.1f} GiB", flush=True)
    del te
    gc.collect(); torch.cuda.empty_cache(); torch.cuda.reset_peak_memory_stats()


def quantize_transformer(src: Path, name: str):
    out = NF4 / f"transformer-{name}"
    if _done(out):
        print(f"[skip] {out} exists", flush=True)
        return
    from diffusers import BitsAndBytesConfig, QwenImage21Transformer2DModel
    cfg = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.bfloat16)
    t0 = time.time()
    print(f"Quantizing {name} transformer (7B DiT) to NF4 ...", flush=True)
    tr = QwenImage21Transformer2DModel.from_pretrained(
        src / "transformer", quantization_config=cfg, torch_dtype=torch.bfloat16, device_map={"": 0})
    out.mkdir(parents=True, exist_ok=True)
    tr.save_pretrained(out, safe_serialization=True)
    print(f"  saved {out} in {time.time() - t0:.0f}s, peak VRAM {torch.cuda.max_memory_allocated() / 2**30:.1f} GiB", flush=True)
    del tr
    gc.collect(); torch.cuda.empty_cache(); torch.cuda.reset_peak_memory_stats()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["text_encoder", "base", "turbo"])
    a = ap.parse_args()
    with gpu_runtime.oom_guard("NF4 quantization", exit_on_oom=True):
        if a.only in (None, "text_encoder"):
            quantize_text_encoder()
        if a.only in (None, "base"):
            quantize_transformer(BASE, "base")
        if a.only in (None, "turbo"):
            quantize_transformer(TURBO, "turbo")
    print("NF4 models ready.", flush=True)


if __name__ == "__main__":
    main()
