#!/usr/bin/env python3
"""MOSS-Image Gradio launcher for udragon (RTX 5070 Ti, 15.4 GiB usable).

Upstream's "16gb" profile defaults to component ("model") CPU offload, which moves the whole
~18GB Qwen3.5-9B text encoder onto the GPU in one go and OOMs here (verified 2026-10-18).
Sequential offload works (~1.2GB peak VRAM, ~3 min per 1024px/50-step image), so make it the
default without editing the upstream clone. Everything else is upstream's gradio_app.main().
"""
import sys
from pathlib import Path

sys.path.insert(0, "/srv/containers/edq/projects/MOSS-Image")
import gradio_app  # noqa: E402  (upstream; imports torch)

_upstream_profile_defaults = gradio_app.profile_defaults


def profile_defaults(profile, vram_gb=None):
    offload, height, width = _upstream_profile_defaults(profile, vram_gb)
    return ("sequential" if offload == "model" else offload), height, width


gradio_app.profile_defaults = profile_defaults

if __name__ == "__main__":
    Path.home().joinpath("ai_generated/moss-image").mkdir(parents=True, exist_ok=True)
    gradio_app.main()
