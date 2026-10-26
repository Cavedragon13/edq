# Qwen-Image 2.1 Studio

Dragonsuite port **8076** · Gradio · Seed 13 purple/gold, dark by default · outputs
`/home/edq/ai_generated/qwen-image-21/` (timestamped `qi21_<date>_<time>_<model>_<t2i|edit|rgba>_<seed>.png`,
settings in the PNG `parameters` text chunk and a `.json` sidecar; `latest.png` = newest).

**License:** Qwen Research License — non-commercial / research only. A commercial license must be requested
from Qwen (model-business@notice.qwencloud.com) before any client or paid work. The UI shows this note.

## What it does
- Text-to-image with the official 7B **Qwen-Image-2.1** (40 steps, steps adjustable) or **Qwen-Image-2.1-Turbo**
  (official 8-step distilled checkpoint, fixed schedule; default).
- Image editing / composition with 1-10 reference images ("Use result as a reference" button chains edits).
- Native transparent RGBA PNGs (checkbox adds the recommended prompt wrapper).
- The 7 official ~4MP aspect presets plus "Match reference image" and a ~1MP fast preview; seed; gallery of recent outputs.

## How it runs on the 16GB card
`scripts/quantize_qwen_image_21.py` makes one-time bitsandbytes NF4 copies of the DiT (3.8G each) and the
Qwen3-VL text encoder (6.3G; vision tower and lm_head stay bf16). The app loads them in ~4s and uses
`enable_model_cpu_offload()`, so only one component is on the GPU at a time, plus VAE tiling for 2K decodes.
VRAM is released after every job. Before each job it re-checks free VRAM and refuses with a clear message
(never unloading another tool) if under 8000 MiB.

## Files
| Piece | Path |
| --- | --- |
| App | `scripts/qwen_image_21_gradio.py` |
| Launcher (vram_guard 9000 MiB / 15000 MiB RAM) | `scripts/start_qwen_image_21.sh` |
| Stop | dashboard `stop_command`: `pkill -f '[q]wen_image_21_gradio.py'` |
| Venv build | `scripts/setup_qwen_image_21_env.sh` + `scripts/requirements_qwen_image_21.txt` |
| Model download | `scripts/download_qwen_image_21_models.sh` → `models/qwen-image-21/` |
| NF4 build | `scripts/quantize_qwen_image_21.py` → `models/qwen-image-21/nf4/` |
| E2E test (through the Gradio API) | `scripts/test_qwen_image_21.py` |
| Logs | `logs/qwen_image_21.log` (app), `logs/qwen_image_21_server.log` (stdout) |

## Verified 2026-10-25 (through the running app's Gradio API, final code)
| Test | Size | Gen time | Peak VRAM (card / torch) |
| --- | --- | --- | --- |
| Turbo t2i, fast preview | 1024² | 16.0s | 7.7 GB / 6.4 GiB |
| Base t2i, 40 steps | 1024² | 40.1s | 7.7 GB / 6.4 GiB |
| Turbo t2i, full 16:9 | 2752×1536 | 47.6s | 7.8 GB / 6.4 GiB |
| Turbo RGBA sticker | 1024² | 10.6s | 7.7 GB / 6.4 GiB — 68.8% fully transparent pixels |
| Turbo edit (1 reference) | 1024² | 13.2s | 9.2 GB / 7.5 GiB |
| Base edit (1 reference) | 1024² | 52.6s | 7.5 GiB torch |
VRAM gate: with 10.5GB held by another process the app refused cleanly and generated normally once it was
released; vram_guard refused an impossible request and passed the real one. Dashboard start/stop/restart
verified (VRAM back to the 863 MiB desktop baseline after stop).
