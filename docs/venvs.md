# Virtual Environment Registry

Centralized tracking of Python virtual environments in this workspace.

## Active Venvs

| Name                    | Path                                              | Size   | Used By                       | Purpose                                                    |
| ----------------------- | ------------------------------------------------- | ------ | ----------------------------- | ---------------------------------------------------------- |
| venv_dragonsuite        | `/srv/containers/edq/venv_dragonsuite`            | ~53MB  | `dragonsuite_server.py`       | Dashboard backend (FastAPI)                                |
| venv_concert_shirt      | `/srv/containers/edq/venv_concert_shirt`          | ~50MB  | `start_concert_shirt.sh`      | Concert History T-Shirt Generator (port 8030)              |
| venv_florence2          | `/srv/containers/edq/venv_florence2`              | ~7GB   | `start_dragonsight.sh`        | Florence2 vision model service                             |
| venv_flux2              | `/srv/containers/edq/venv_flux2`                  | ~7GB   | `start_flux2_klein.sh`        | DragonFlux Klein + Street View Studio (shared GPU stack)   |
| venv_wan2gp             | `/srv/containers/edq/venv_wan2gp`                 | ~9GB   | `start_wan2gp.sh`             | Wan2GP video generation                                    |
| venv_fish_speech        | `/srv/containers/edq/venv_fish_speech`            | ~8GB   | `start_fish_speech.sh`        | Fish Speech TTS (Fish Audio S2-Pro, 4B)                    |
| venv_heartmula          | `/srv/containers/edq/venv_heartmula`              | ~12GB  | `start_heartmula.sh`          | HeartMuLa music generation (3B)                            |
| venv_sam2               | `/srv/containers/edq/venv_sam2`                   | ~6GB   | `start_sam2.sh`               | SAM 2.1 image/video segmentation                           |
| venv_liveportrait       | `/srv/containers/edq/venv_liveportrait`           | ~8GB   | `start_liveportrait.sh`       | LivePortrait portrait animation (KlingTeam)                |
| venv_hunyuan3d          | `/srv/containers/edq/venv_hunyuan3d`              | ~10GB  | `start_hunyuan3d.sh`          | Hunyuan3D-2 image to 3D                                    |
| venv_qwen3_tts          | `/srv/containers/edq/venv_qwen3_tts`              | ~8GB   | `start_qwen3_tts.sh`          | Qwen3-TTS (TTS, cloning, voice design)                     |
| venv_realesrgan         | `/srv/containers/edq/venv_realesrgan`             | ~4GB   | `start_realesrgan.sh`         | Real-ESRGAN image upscaling                                |
| venv_zimage             | `/srv/containers/edq/venv_zimage`                 | ~8GB   | `start_zimage.sh`             | Z-Image Base/Turbo + Z-Anime shared image runtime          |
| venv_rembg              | `/srv/containers/edq/venv_rembg`                  | ~1GB   | `start_rembg.sh`              | Rembg AI background removal                                |
| venv_qwen_image_layered | `/srv/containers/edq/venv_qwen_image_layered`     | ~10GB  | `start_qwen_image_layered.sh` | Qwen-Image-Layered decomposition                           |
| venv_mule_game          | `/srv/containers/edq/venv_mule_game`              | ~50MB  | `start_mule_game.sh`          | M.U.L.E. web game (Gradio)                                 |
| venv_facefusion         | `/srv/containers/edq/venv_facefusion`             | ~2GB   | `start_facefusion.sh`         | FaceFusion face swap & manipulation                        |
| ACE-Step .venv          | `/srv/containers/edq/projects/ACE-Step-1.5-xl/.venv` | ~5GB   | `start_ace_step.sh`           | ACE-Step 1.5 XL music generation (managed by uv)           |
| venv_soulxsinger        | `/srv/containers/edq/venv_soulxsinger`            | ~8GB   | `start_soulxsinger.sh`        | SoulX-Singer zero-shot singing voice synthesis             |
| venv_deepgen            | `/srv/containers/edq/venv_deepgen`                | ~7GB   | `start_deepgen.sh`            | DeepGen 1.0 diffusers image gen/edit (5B)                  |
| JustDubit .venv         | `/srv/containers/edq/projects/just-dub-it/.venv`  | ~8GB   | `start_justdubit.sh`          | JustDubit video dubbing (managed by uv)                    |
| venv_topaz_gradio       | `/srv/containers/edq/venv_topaz_gradio`           | ~300MB | `start_topaz_labs.sh`         | Topaz Labs Gradio web UI (cloud API client)                |
| venv_dolphin_vision     | `/srv/containers/edq/venv_dolphin_vision`         | ~8GB   | `start_dolphin_vision.sh`     | Dolphin Vision 7B uncensored VLM (BunnyQwen2 architecture) |
| venv_wan_1b             | `/srv/containers/edq/venv_wan_1b`                 | ~8GB   | `start_wan_1b.sh`             | Wan2.1-T2V-1.3B text-to-video (diffusers, port 8016)       |
| venv_ltxvideo           | `/srv/containers/edq/venv_ltxvideo`               | ~10GB  | `start_ltxvideo.sh`           | LTX-Video-0.9.7-distilled T2V+I2V (diffusers, port 8028)   |
| venv_dragonsong         | `/srv/containers/edq/venv_dragonsong`             | ~50MB  | `start_dragonsong.sh`         | Dragonsong - Google Lyria RealTime music (port 8029)       |
| venv_lavasr             | `/srv/containers/edq/venv_lavasr`                 | ~2GB   | `start_lavasr.sh`             | LavaSR speech enhance + BWE upsample to 48kHz (port 8034)  |
| venv_the_movies         | `/srv/containers/edq/venv_the_movies`             | ~50MB  | `start_the_movies.sh`         | The Movies AI film studio sim (port 8035)                  |
| venv_tada               | `/srv/containers/edq/venv_tada`                   | ~5GB   | `start_tada.sh`               | TADA TTS (Hume AI TADA-3B-ML, port 8037)                   |
| venv_matanyone2         | `/srv/containers/edq/venv_matanyone2`             | ~8GB   | `start_matanyone2.sh`         | MatAnyone 2 human video matting (port 8038)                |
| venv_voxtral            | `/srv/containers/edq/venv_voxtral`                | ~8GB   | `start_voxtral.sh`            | Voxtral TTS (Mistral Voxtral-4B-TTS-2603, port 8042)       |
| venv_streetview         | `/srv/containers/edq/venv_streetview`             | ~200MB | (fetch-only fallback)         | Lightweight fetch-only venv — superseded by venv_flux2     |
| venv_dragonweyr         | `/srv/containers/edq/venv_dragonweyr`             | ~300MB | `start_dragonweyr.sh`         | Polymarket scout + Claude proxy + CLOB execution port 8046 |
| venv_kalshi             | `/srv/containers/edq/venv_kalshi`                 | ~300MB | `start_kalshi.sh`             | Kalshi scout + Claude proxy + RSA-auth order exec (8047)   |
| venv_agentic_video      | `/srv/containers/edq/venv_agentic_video`          | ~3GB   | `start_agentic_video.sh`      | Agentic Video Editor — 4-agent pipeline (port 8044)        |
| venv_unsloth_studio     | `/srv/containers/edq/venv_unsloth_studio`         | ~8GB   | `start_unsloth_studio.sh`     | Unsloth Studio — LoRA/QLoRA/RL LLM fine-tuning (port 8050) |

## MCP Server Venvs

| Name                 | Path                                                    | Size  | Purpose                                               |
| -------------------- | ------------------------------------------------------- | ----- | ----------------------------------------------------- |
| dragonsuite-mcp      | `/srv/containers/edq/mcp-servers/dragonsuite/venv`      | ~20MB | Dragonsuite MCP server for Claude Code                |
| topaz-labs-mcp       | `/srv/containers/edq/mcp-servers/topaz-labs/venv`       | ~20MB | Topaz Labs API MCP server for image/video enhancement |
| vocab-translator-mcp | `/srv/containers/edq/mcp-servers/vocab-translator/venv` | ~20MB | Vocab translator MCP server with Ollama backend       |
| mcp-inspector        | `/srv/containers/edq/venv_mcp_inspector`                | ~30MB | MCP Inspector web app with Supabase integration       |

## Naming Convention

- Centralized venvs: `/srv/containers/edq/venv_<project>`
- Exceptions:
  - ComfyUI keeps its venv inside project dir (standard for ComfyUI)
  - ACE-Step uses `uv` package manager with `.venv` in project dir
  - JustDubit uses `uv` package manager with `.venv` in project dir

## Cleanup Checklist

When removing a project:

1. Delete the venv directory
2. Remove from this registry
3. Remove from `config/dragonsuite.json`
4. Delete associated scripts in `scripts/`

## History

| Date       | Action                                                                                                                   |
| ---------- | ------------------------------------------------------------------------------------------------------------------------ |
| 2026-01-20 | Deleted `venv_qwen` (477MB) - Qwen legacy removed                                                                        |
| 2026-01-20 | Deleted orphan `/Wan2GP/.venv` (9.2GB) - duplicate of projects/Wan2GP                                                    |
| 2026-01-20 | Deleted orphan `/Wan2GP/` (63GB total) - script uses projects/Wan2GP                                                     |
| 2026-01-20 | Deleted empty `projects/wan-animate/venv` (32K)                                                                          |
| 2026-01-20 | Created this registry                                                                                                    |
| 2026-01-23 | Added `venv_heartmula` for HeartMuLa music generator                                                                     |
| 2026-01-23 | Added `venv_sam2`, `venv_sadtalker`, `venv_hunyuan3d`, `venv_matanyone`                                                  |
| 2026-01-24 | Added `venv_qwen3_tts` for Qwen3-TTS (1.7B models)                                                                       |
| 2026-01-24 | Added `venv_realesrgan` for Real-ESRGAN upscaling                                                                        |
| 2026-01-25 | Deleted `comfyui-wan/venv` (129GB) - ComfyUI removed from Dragonsuite                                                    |
| 2026-01-29 | Added `venv_zimage` for Z-Image Base (Alibaba Tongyi 6B)                                                                 |
| 2026-01-31 | Added `venv_rembg` for Rembg AI background removal                                                                       |
| 2026-01-31 | Added `venv_qwen_image_layered` for Qwen-Image-Layered decomposition                                                     |
| 2026-02-01 | Added MCP servers section; created `mcp-servers/dragonsuite/venv`                                                        |
| 2026-02-01 | Deleted `venv_matanyone` - dependency conflicts, SAM2+Rembg cover use cases                                              |
| 2026-02-02 | Replaced `venv_sadtalker` with `venv_liveportrait` (KlingTeam, 2026)                                                     |
| 2026-02-06 | Added `venv_mule_game` for M.U.L.E. web game (tribute to Dani Bunten Berry)                                              |
| 2026-02-08 | Added `venv_facefusion` for FaceFusion face swap & manipulation                                                          |
| 2026-02-08 | Added `topaz-labs-mcp` MCP server for Topaz Labs API integration                                                         |
| 2026-02-11 | Added ACE-Step 1.5 (uv-managed .venv) for ultra-fast music generation                                                    |
| 2026-02-11 | Added Z-Image-Fun-Lora-Distill fast mode (4-step/8-step LoRAs)                                                           |
| 2026-02-15 | Added `venv_soulxsinger` for SoulX-Singer zero-shot singing synthesis                                                    |
| 2026-02-15 | Added `venv_deepgen` for DeepGen 1.0 multimodal image gen/edit                                                           |
| 2026-02-15 | Added JustDubit .venv (uv-managed) for video dubbing with lip-sync                                                       |
| 2026-02-15 | Added `venv_topaz_gradio` for Topaz Labs Gradio web UI (separate from MCP venv)                                          |
| 2026-02-15 | Added `venv_dolphin_vision` for Dolphin Vision 7B uncensored VLM (port 8025)                                             |
| 2026-02-15 | Added AudioMass web audio editor - Audacity-like client-side editor (port 8027)                                          |
| 2026-02-15 | Added Audio Processing Suite - exposes SoulX-Singer preprocess models standalone (port 8026)                             |
| 2026-02-15 | Enhanced DragonFlux Klein - added FLUX.1-dev HD Mode as third model option                                               |
| 2026-02-18 | Added `venv_wan_1b` for Wan2.1-T2V-1.3B standalone video generation (port 8016)                                          |
| 2026-02-18 | Added `venv_ltxvideo` for LTX-Video-0.9.7-distilled T2V+I2V standalone (port 8028)                                       |
| 2026-03-01 | Added `venv_lavasr` for LavaSR speech enhancement + BWE upsampling to 48kHz (port 8034)                                  |
| 2026-03-02 | Added `venv_the_movies` for The Movies AI film studio sim (port 8035)                                                    |
| 2026-03-12 | Attempted `venv_nemotron` for Nemotron Nano 9B v2 — removed; mamba-ssm/Blackwell incompat.                               |
| 2026-03-15 | Updated `venv_fish_speech` — Fish Speech v2.0.0 / Fish Audio S2-Pro (4B)                                                 |
| 2026-03-15 | Added `venv_tada` for TADA TTS (Hume AI TADA-3B-ML, port 8037)                                                           |
| 2026-03-15 | Added `venv_matanyone2` for MatAnyone 2 video matting CVPR 2026 (port 8038)                                              |
| 2026-04-17 | Added `venv_voxcpm2` for VoxCPM2 2B diffusion TTS — 48kHz, 30+ languages, voice design & cloning (port 8048)             |
| 2026-04-19 | Added `venv_agentic_video` for Agentic Video Editor 4-agent pipeline (Director/Trimmer/Editor/Reviewer) (port 8044)      |
| 2026-04-19 | Added Docker service for OmniVoice-Studio cinematic video dubbing (port 8051, remapped from container's :8000)           |
| 2026-04-19 | Installed Claude Code skills: Waza (8 skills: /think /design /check /hunt /write /learn /read /health)                   |
| 2026-04-19 | Installed Claude Code skills: caveman (6 compression skills: /caveman /caveman-compress /caveman-commit /caveman-review) |
| 2026-05-04 | Updated `venv_zimage` — now shared with Z-Anime (port 8008); venv_zimage entry updated in registry                       |
