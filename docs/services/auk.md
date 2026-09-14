# AuK — speech generation + editing (Tencent Hunyuan)

Added 2026-09-13. Port **8065**. Category: audio. GPU (on-demand, lazy-loaded).

| Item | Value |
| --- | --- |
| Model | [tencent/AuK](https://huggingface.co/tencent/AuK) 1.5B rectified-flow DiT + VAE; [tencent/AuK-Flash](https://huggingface.co/tencent/AuK-Flash) 4-step distilled; MLLM encoder [Qwen/Qwen2.5-Omni-3B](https://huggingface.co/Qwen/Qwen2.5-Omni-3B) |
| License | MIT (code + weights) |
| Repo | `projects/AuK` (github.com/Tencent-Hunyuan/AuK, released 2026-09-09) |
| Venv | `venv_auk` (Python 3.10, torch 2.7.1+cu128 — upstream pins torch <2.8) |
| Launcher | `scripts/start_auk.sh` → `scripts/auk_gradio.py` (wraps the vendor `auk.infer.infer_gradio` demo) |
| Models | `scripts/download_auk_models.sh` → `models/auk/{AuK,AuK-Flash,Qwen2.5-Omni-3B}` |
| Output | `~/ai_generated/auk/auk_<task>_<stamp>.wav` + `latest.wav` (the vendor demo only returns audio to the browser; the wrapper persists it) |
| VRAM | Upstream (A800, bf16): 24.8 GiB, **16.75–16.98 GiB with `--cpu_offload`**. Measured here: see venvs.md history row. |

## Tasks (one natural-language instruction interface)

Zero-shot TTS (voice from reference audio), instruct TTS (voice from a description), speech
content editing, lyric editing, pitch / speed / volume editing, emotion / timbre / de-accent /
nonverbal / whisper conversion, speech enhancement, speech & music separation, target-speaker
extraction. Instruction templates: `projects/AuK/docs/COOKBOOK.md`.

## Launcher behaviour

- `AUK_VARIANT=base` (default) exposes only the base model; `flash` only AuK-Flash; `both`
  exposes both (two engines resident ≈ 2× VRAM — not for this card).
- Always launched with `--cpu_offload` (Qwen encoder + DiT swap to CPU when idle, VAE stays
  on CUDA). The port comes up in seconds; the engine loads on the first request.
- Dashboard link opens `/?__theme=dark`; the wrapper also sets dark mode with
  `localStorage['auk-theme']`.
- The vendor demo's example clips resolve relative to the repo, so the launcher `cd`s into
  `projects/AuK` before starting.
