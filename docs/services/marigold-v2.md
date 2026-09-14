# Marigold V2 — depth / normals / albedo (via ComfyUI)

Added 2026-09-13. Port **8066** (front-end); ComfyUI backend on 8188. Category: vision. GPU.

| Item | Value |
| --- | --- |
| Model | [huawei-bayerlab/marigold-v2-0](https://huggingface.co/huawei-bayerlab/marigold-v2-0) — rank-128 LoRA + fine-tuned VAE decoder per modality over Qwen-Image-Edit-2509 (20B DiT). SIGGRAPH Asia 2026 / ACM TOG. |
| License | Weights Apache-2.0; base model keeps the Qwen-Image-Edit license (Apache-2.0) |
| Backbone here | [QuantStack/Qwen-Image-Edit-2509-GGUF](https://huggingface.co/QuantStack/Qwen-Image-Edit-2509-GGUF) **Q4_K_S** (12.2 GB) through ComfyUI-GGUF |
| Nodes | `custom_nodes/ComfyUI-Marigold-v2` (visualbruno) + `custom_nodes/ComfyUI-GGUF` (city96); ComfyUI updated v0.33.3 → **v0.35.1** for this |
| Venv | `venv_marigold_v2` (front-end only: gradio + requests). Model deps (peft, bitsandbytes, diffusers, opencv) live in `venv_comfyui` |
| Launcher | `scripts/start_marigold_v2.sh` (starts ComfyUI if needed) → `scripts/marigold_v2_gradio.py` |
| Models | `scripts/download_marigold_v2_models.sh` → `projects/ComfyUI/models/{unet,vae,loras,marigold-v2/…}` |
| Output | `~/ai_generated/marigold-v2/marigold_v2_<depth|normals|albedo|color>_<stamp>.png`, optional `_raw_<stamp>.npy`, `latest_<modality>.png` |
| VRAM | Official code: ~17 GB at 1024², 29 GB at 2048² — **does not fit 16 GB**, which is why this runs as a GGUF workflow inside ComfyUI. Measured here: see venvs.md history row. |

## Why ComfyUI and not a standalone service

The standalone reference implementation loads the full DiT (4-bit via bitsandbytes) and needs
17 GB at the 1024² working resolution. The only path under 16 GB is a GGUF-quantized backbone,
and ComfyUI-GGUF is the mature loader for that. So this is the one Dragonsuite service that is a
thin front-end over ComfyUI rather than its own process: the front-end holds no model, submits an
API-format workflow (`UnetLoaderGGUF → MarigoldV2LoRALoader → MarigoldV2Predict → SaveImage`,
plus `MarigoldV2ColorizeDepth` for depth) and copies the results into `ai_generated/`.

## Operational notes

- First prediction loads the 12 GB backbone (a minute or two); `keep_model_loaded=True` keeps
  it resident inside ComfyUI for the next call. Stopping the Marigold card stops only the
  front-end; stop the **ComfyUI** card to free the GPU.
- Text encoder is never loaded — Marigold ships precomputed prompt embeddings per modality
  (`models/marigold-v2/Marigold-V2/qwen_text_embeddings/`).
- Depth output is affine-invariant log depth (`Log-stage2` checkpoint); "near = bright"
  toggles the convention. The colorized PNG uses matplotlib `Spectral_r` by default.
- The example workflows shipped with the node pack are in
  `custom_nodes/ComfyUI-Marigold-v2/example_workflows/` if you want to drive it from the
  ComfyUI graph editor instead.
