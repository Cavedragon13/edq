#!/usr/bin/env python3
"""
AuK — Tencent's 1.5B speech generation + editing model (zero-shot / instruct
TTS, content & lyric editing, pitch/speed/volume, emotion/timbre/accent,
enhancement, separation).

Thin Dragonsuite wrapper around the vendor Gradio demo
(`auk.infer.infer_gradio`): keeps the upstream UI and task presets intact, and
adds the house rules — every result is also written to ~/ai_generated/auk/ with
a timestamp, mid-generation CUDA OOM becomes a clean UI error via gpu_runtime,
and the page defaults to dark mode.
Dragonsuite port 8065.
"""

import gpu_runtime  # noqa: F401  — must precede torch (CUDA allocator config)

import os
import shutil
import sys
import wave
from datetime import datetime
from pathlib import Path

import gradio as gr
from auk.infer import infer_gradio as ig

OUTPUT_DIR = Path(os.path.expanduser("~/ai_generated/auk"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

_upstream_run_generate = ig.run_generate


def _save_pcm16(sample_rate: int, pcm16, tag: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUTPUT_DIR / f"auk_{tag}_{stamp}.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(sample_rate))
        w.writeframes(pcm16.tobytes())
    shutil.copy2(path, OUTPUT_DIR / "latest.wav")
    return path


def run_generate(variant, audio, instruction, gen_seconds, ref_text, gen_text, nfe, cfg, seed, task_type=None):
    """Upstream handler + persistent, timestamped output + clean OOM handling."""
    try:
        with gpu_runtime.oom_guard("AuK generation"):
            sample_rate, pcm16 = _upstream_run_generate(
                variant, audio, instruction, gen_seconds, ref_text, gen_text, nfe, cfg, seed, task_type=task_type
            )
    except RuntimeError as exc:
        raise gr.Error(str(exc))
    tag = (task_type or "gen").replace(" ", "_").replace("/", "-").lower()[:24]
    path = _save_pcm16(sample_rate, pcm16, tag)
    print(f"  saved {path.name}  ({len(pcm16) / sample_rate:.1f}s @ {sample_rate} Hz)")
    return sample_rate, pcm16


ig.run_generate = run_generate  # build_demo() and run_generate_with_pe resolve this name at build/call time

# Dark by default with localStorage persistence (house rule). Blocks.js is
# consulted when the page config is served, so set it after build_demo().
DARK_JS = """
() => {
  const pref = localStorage.getItem('auk-theme') || 'dark';
  document.body.classList.toggle('dark', pref === 'dark');
}
"""
_upstream_build_demo = ig.build_demo


def build_demo():
    demo = _upstream_build_demo()
    demo.js = DARK_JS
    return demo


ig.build_demo = build_demo

if __name__ == "__main__":
    print("AuK")
    print("===")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Args: {' '.join(sys.argv[1:])}")
    ig.main()
