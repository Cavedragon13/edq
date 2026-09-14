# YuE2 — full-song music generation with editable scores

Added 2026-09-13. Port **8064**. Category: music. GPU (on-demand).

| Item | Value |
| --- | --- |
| Model | [m-a-p/YuE2-3B](https://huggingface.co/m-a-p/YuE2-3B) (3.59B AR–NAR Mixture-of-Transformers) + [m-a-p/YuE2-Vae](https://huggingface.co/m-a-p/YuE2-Vae) (48 kHz stereo decoder) |
| License | Weights CC BY-NC 4.0 (non-commercial) |
| Inference package | `yue2_infer-0.1.5` wheel shipped inside the model repo (`from yue2 import YuE2Pipeline`) |
| Venv | `venv_yue2` (Python 3.12, torch 2.10.0+cu128) |
| Launcher | `scripts/start_yue2.sh` → `scripts/yue2_gradio.py` |
| Models | `scripts/download_yue2_models.sh` → HF hub cache (the pipeline resolves repo ids through the cache) |
| Output | `~/ai_generated/yue2/` — `yue2_<song|cover>_<stamp>.flac` + `.mp3`, `latest.flac/.mp3`, and a per-song folder with `score.abc`, `plan.json`, latents |
| VRAM | Upstream: 11.2 GiB typical, 14.1 GiB max-context on a 4090 (BF16, no quantization). Launcher declares `REQ_VRAM_MIB=14500`. Measured here: see venvs.md history row. |

## What it does

Lyrics with `[Verse]/[Chorus]/…` labels + a style prompt → a complete song with vocals and
accompaniment. `cot="full"` first writes an ABC score (melody + chords) which you can edit and
re-render; `cot="melody"` is the recommended mode for covers from a melody-only ABC transcription.

Benchmarks (WildSongBench, from the model card): SongBench avg 6.73 single / 6.96 best-of-8,
vs Suno v5 6.87 and MiniMax Music 3 6.28 (which we also run, port 8059).

## UI

- **Create** tab — style, lyrics, planning mode, 16/32 ODE steps, seed, text-guidance slider
  (passes `cfg_scale` only when > 1.0 so model defaults stay intact).
- **From score** tab — paste an ABC score (edited `score.abc`, or a melody-only transcription)
  and render it in a new style. SheetSage2 (audio → ABC) is **not** bundled; it needs its own
  venv (torch 2.8 / transformers 4.45) per upstream.
- Dark by default, persisted in `localStorage['yue2-theme']`; 🌙/☀️ toggle top-right.

## Notes

- One song at a time (`default_concurrency_limit=1`). A 3.6-min song took ~71 s on a 4090;
  expect roughly 2× that here.
- Upstream asks for ~24 GB free host RAM; we have 31 GB total — close other RAM-heavy
  services (SenseNova-class loaders) first.
- Community GGUF/audio.cpp builds exist (Q8 < 9 GB VRAM) if the BF16 pipeline ever needs
  to coexist with another GPU tool; not used here.
