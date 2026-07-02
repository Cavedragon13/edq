# CLAUDE.md

Guidance for Claude Code working in this personal AI development environment on udragon (Ubuntu 24.04, RTX 5070 Ti Blackwell).

## Canonical Host

**udragon is the source of truth.** Dragonsuite apps, service launchers, API keys, docs, project repos, model caches, and generated outputs live under `/srv/containers/edq` on udragon (`192.168.7.226`). Mac hosts such as cdragon are clients for browsing, editing, SSH, SMB/Obsidian access, and light local work; do not infer that a project should live on cdragon because a local shell or SSH alias resolves there. When in doubt, SSH to udragon and work from `/srv/containers/edq`.

## Directory Structure

```
/srv/containers/edq/
├── .env                # API keys — single source of truth, NEVER duplicate
├── .mcp.json           # MCP server config — NEVER duplicate
├── config/             # dragonsuite.json (service registry)
├── scripts/            # Shell launchers (start_*.sh) and Python scripts
├── docs/               # Architecture patterns, service docs, venvs.md
├── projects/           # Cloned AI project repos (self-contained)
├── models/             # Downloaded AI model weights
├── media/              # HTML apps, media files
├── mcp-servers/        # Custom MCP server implementations
├── venv_*/             # Virtual environments (see docs/venvs.md)
└── cache_huggingface/  # HF hub cache (symlinked from ~/.cache/huggingface)
```

## Port Layout

| Port                                     | Service                  | Type                             | Notes                                                                          |
| ---------------------------------------- | ------------------------ | -------------------------------- | ------------------------------------------------------------------------------ |
| 1234                                     | LM Studio API            | On-demand (manual)               |                                                                                |
| 3000                                     | Remotion Studio          | Always-on (systemd)              | Video composition/render, remotion-test project                                |
| 8001                                     | DragonFlux Klein         | On-demand (GPU)                  | FLUX.2-klein + FLUX.1-dev HD + LoRA                                            |
| 8002                                     | WanGP2                   | On-demand (GPU)                  | Video generation (Wan 2.0)                                                     |
| 8003                                     | Fish Speech              | On-demand (GPU)                  | Expressive TTS + voice cloning                                                 |
| 8004                                     | HeartMuLa                | On-demand (GPU)                  | Music gen from lyrics (~12GB VRAM)                                             |
| 8005                                     | SAM 2.1                  | On-demand (GPU)                  | Image/video segmentation                                                       |
| 8006                                     | LivePortrait             | On-demand (GPU)                  | Portrait animation + expression transfer                                       |
| 8007                                     | Hunyuan3D-2              | On-demand (GPU)                  | Image to 3D mesh                                                               |
| 8008                                     | Z-Anime                  | On-demand (GPU)                  | Anime fine-tune of Z-Image Base, 6B S3-DiT                                     |
| 8009                                     | Qwen3-TTS                | On-demand (GPU)                  | High-quality TTS + voice design                                                |
| 8010                                     | Real-ESRGAN              | On-demand (GPU)                  | AI upscaling, multiple models                                                  |
| 8011                                     | Z-Image Base             | On-demand (GPU)                  | Alibaba 6B text-to-image (Base/Turbo/Fast)                                     |
| 8012                                     | Rembg                    | On-demand (GPU)                  | Background removal                                                             |
| 8013                                     | Qwen-Image-Layered       | On-demand (GPU)                  | Layer decomposition for image editing                                          |
| 8014                                     | Qwen3-Audiobook          | On-demand                        | Document to audiobook                                                          |
| 8015                                     | DragonArt Studio         | Production                       | 70+ image modes + Street View capture (React)                                  |
| 8016                                     | Wan2.1 T2V 1.3B          | On-demand (GPU)                  | T2V, sequential CPU offload, diffusers                                         |
| 8017                                     | FaceFusion               | On-demand (GPU)                  | Face swap + enhancement                                                        |
| 8018                                     | Creative Upscaler        | On-demand (GPU)                  | AI upscaling with style transfer                                               |
| 8019                                     | Bonsai MLX Studio        | On-demand (Mac MLX)              | Apple Silicon image gen, frontend on 192.168.7.131; backend on :8040 same host |
| 8020                                     | MCP Inspector            | On-demand                        | Security auditing for MCP servers                                              |
| 8021                                     | ACE-Step 1.5 XL          | On-demand (GPU)                  | Ultra-fast music gen (<4GB VRAM)                                               |
| 8022                                     | JustDubit                | On-demand (GPU)                  | TTS / audio synthesis                                                          |
| 8023                                     | SoulX-Singer             | On-demand (GPU)                  | AI singing voice synthesis                                                     |
| 8024                                     | DeepGen 1.0              | On-demand (GPU)                  | Image generation                                                               |
| 8025                                     | Dolphin Vision 7B        | On-demand (GPU)                  | Uncensored VLM image Q&A                                                       |
| 8026                                     | Dragon Audio Workstation | On-demand (GPU)                  | Enhance+48kHz, Stems, Dereverb, ASR, /editor/                                  |
| 8027                                     | Foundation-1             | On-demand (GPU)                  | Music generation                                                               |
| 8028                                     | LTX-Video 0.9.8-13B      | On-demand (GPU)                  | T2V+I2V, 7-step distilled, 3-pass upscale                                      |
| 8029                                     | Dragonsong               | On-demand                        | Lyria RealTime music — live steering + record                                  |
| 8030                                     | Horse Racing v2          | On-demand                        | Win/Place/Show betting, parlay, AI opponents                                   |
| 8031                                     | Interactive Games        | On-demand                        | Survival Series, Lunar Reckoning, text adventures                              |
| 8032                                     | M.U.L.E.                 | On-demand                        | Economic strategy game                                                         |
| 8033                                     | Concert Shirt            | On-demand                        | Ticket OCR to concert list to print-on-demand                                  |
| 8035                                     | The Movies               | On-demand                        | AI film studio — Nano Banana 2 + Veo + Lyria                                   |
| 8036                                     | Mercury2 Diffusion Chat  | On-demand                        | Inception Labs diffusion LLM                                                   |
| 8037                                     | TADA TTS                 | On-demand (GPU)                  | Hume AI voice cloning, 9 languages                                             |
| 8038                                     | MatAnyone 2              | On-demand (GPU)                  | Human video matting, click-to-select                                           |
| 8039                                     | Linkding                 | On-demand                        | Cross-browser bookmark manager (Docker)                                        |
| 8041                                     | AI Toolkit               | On-demand (GPU)                  | LoRA trainer for FLUX                                                          |
| 8042                                     | Voxtral TTS              | On-demand (GPU)                  | Mistral Voxtral-4B-TTS, 20 voices, 9 languages                                 |
| 8043                                     | Gemma 4 12B              | On-demand                        | Default 12B unified multimodal; E4B toggle, Ollama                             |
| 8044                                     | Agentic Video Editor     | On-demand (GPU)                  | 4-agent pipeline — Director/Trim/Editor/Review                                 |
| 8045                                     | M.U.L.E. 3               | On-demand                        | M.U.L.E. remake — canvas, AI opponents, auctions                               |
| 8046                                     | Dragonweyr               | On-demand                        | Polymarket scout + Claude AI + CLOB execution                                  |
| 8047                                     | Dragonweyr-Kalshi        | On-demand                        | Kalshi scout + Claude AI + order execution                                     |
| 8048                                     | Trading Dashboard        | On-demand                        | Paper trading dashboard                                                        |
| 8049                                     | VoxCPM2                  | On-demand (GPU)                  | 2B diffusion TTS, 48kHz, 30+ languages                                         |
| 8050                                     | Unsloth Studio           | On-demand (GPU)                  | LLM fine-tuning — LoRA/QLoRA/RL                                                |
| 8051                                     | OmniVoice Studio         | On-demand (GPU)                  | Cinematic dubbing — transcribe/translate/voice                                 |
| 8052                                     | HiDream-O1-Image-Dev     | On-demand (GPU)                  | Pixel-level unified 8B — T2I + editing                                         |
| 8055                                     | Deep Cut Generator       | On-demand                        | Typography POD concepts, print files, teasers                                  |
| 8056                                     | ballpark-fingerprint     | Manual (Mac, not in Dragonsuite) | Personal FastAPI project; runs on 192.168.7.131, started manually              |
| 8057                                     | Odysseus                 | On-demand (Docker)               | Self-hosted AI workspace: chat, agents, research, docs, email, calendar        |
| 8060                                     | Downloads Gallery        | Always-on (systemd)              | Downloads + any service output folder via card chips; lightbox                 |
| 8062                                     | Krea 2 Turbo             | On-demand (GPU)                  | Krea 2 Turbo image generation + LoRA inference via stable-diffusion.cpp CUDA   |
| 8080                                     | Dragonsight 4.6          | On-demand (GPU)                  | Vision AI + smart naming + Gemma 4 multimodal                                  |
| 8100                                     | Dragonsuite Dashboard    | On-demand                        | Central launcher hub (start here)                                              |
| **udragon always-on**                    |                          |                                  |                                                                                |
| 11434                                    | Ollama API               | Always-on (systemd)              | v0.30.6, official binary /usr/local/bin/ollama; MAX_LOADED_MODELS=1            |
| 21115-21119                              | RustDesk Server          | Always-on (Docker)               | hbbs+hbbr; clients use Tailscale 100.100.225.124                               |
| **minidragon (192.168.7.114) always-on** |                          |                                  |                                                                                |
| 2283                                     | Immich                   | Always-on                        | Photo/video library                                                            |
| 4533                                     | Navidrome                | Always-on                        | Music streaming, FLAC-native                                                   |
| 8096                                     | Jellyfin                 | Always-on                        | Movie/TV/music/photo, Intel QSV transcode                                      |
| 8123                                     | Home Assistant           | Always-on                        | Smart home automation                                                          |
| 9000                                     | Portainer                | Always-on                        | Docker management UI                                                           |
| 25600                                    | Komga                    | Always-on                        | Comics/ebooks — CBR/CBZ/EPUB/PDF                                               |

## Quick Start

```bash
cd /srv/containers/edq
bash scripts/start_dragonsuite.sh            # dashboard → http://192.168.7.226:8100
bash scripts/start_<service>.sh              # any individual service
python3 scripts/health_check.py --all        # structural check, all 65 services
```

## API Keys

Central `.env` at `/srv/containers/edq/.env` — load with `from dotenv import load_dotenv` (Python) or `source /srv/containers/edq/.env` (bash). Keys: `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `ANTHROPIC_API_KEY`. Google keys are from the **'vscode'** Cloud project — enable new APIs there.

**Browser SPAs must never expose keys.** Proxy via the Python server: Browser → `/api/proxy` → Python → external API.

## Hardware

- **GPU**: RTX 5070 Ti, 16GB VRAM, Blackwell (sm_120 / CUDA 12.0)
- **PyTorch**: `pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128`
- **OOM fix**: `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` in launcher
- Only one GPU-heavy service at a time. See `docs/venvs.md` for venv registry.

## Core Rules

1. **RTFM before writing.** Before any external API/SDK/CLI call: read docs, verify exact method names. Wrong names fail completely. Run `/rtfm` skill after writing any API code.
2. **Do the work yourself.** Never ask the user to run commands or paste output — use Bash, filesystem, Playwright, MCP tools directly.
3. **Syntax-check before done.** Python: `python3 -m py_compile`. HTML JS: extract script blocks and validate with node. See CLAUDE.md history for the full command template.
4. **Generative output sanity before done.** Run a representative prompt, inspect the actual file, confirm it follows the prompt. Outputs must land in `~/ai_generated/<service>/` with timestamps.
5. **Dark mode always required.** Every web UI defaults to dark on first load with localStorage persistence. See `knowledge-base/claude-sync/web_ui_patterns.md` for the full standard.

## Test Artifacts & Cleanup

- Real user-facing generated media belongs in `/home/edq/ai_generated/<service>/` with timestamped filenames.
- Smoke tests, one-step sanity checks, audit runs, screenshots, API response samples, and other throwaway outputs belong in `/home/edq/ai_generated/test-artifacts/<type>/`, usually `images/`, `videos/`, `api-responses/`, or `screenshots/`.
- Do not put throwaway test output in `/home/edq/Downloads`, Mac Downloads, the root of iCloud `1Projects`, or a service's user-facing gallery/output folder.
- `scripts/cleanup_test_artifacts.sh` prunes test artifacts older than 30 days. Keep logs and internal traces in service log folders unless they are part of a deliberate audit artifact.

## Transcript Mining

- Claude/Codex JSONL transcripts are valid historical research material for old ideas, lessons, preferences, and house patterns.
- Read `/home/edq/knowledge-base/claude-sync/transcript_mining.md` before mining transcripts. Treat them as leads, verify live facts, and promote durable nuggets into shared docs such as `feedback_log.md`, `global-CLAUDE.md`, `directory_map.md`, or focused topic notes.

## SOPs

**Model downloads:** NEVER let first launch download models. Create `scripts/download_<service>_models.sh` using `snapshot_download()`, run to completion before declaring done. See `docs/sop-model-downloads.md`.

**New service checklist** (use `dragonsuite-add` skill):

- venv at `venv_<service>` + entry in `docs/venvs.md`
- start script in `scripts/`, stop_command in `config/dragonsuite.json`
- `output_dir` set in `config/dragonsuite.json` for all generative services
- `~/ai_generated/<service>/` directory exists on disk
- Verify VRAM drops to baseline after stop (`nvidia-smi`)

## Shorthand Commands

**`llkb`** — update memory files + today's Obsidian daily note + CLAUDE.md (port table and service facts ONLY — never add sections, lessons, or patterns here; those go in memory files). "No summary" is not acceptable.

**`tasks/lessons.md`** — append after any correction immediately:
`- YYYY-MM-DD: [what failed] → [rule going forward]`
Read at session start and apply all rules.

## MCP Server Policy

Default active: `dragonsuite` (project), `gbrain` + `sqlite` (user). Everything else is in `_pool` — move to `mcpServers` in `.mcp.json` and restart VSCodium to enable.

| Server             | Enable for                                        |
| ------------------ | ------------------------------------------------- |
| `github`           | GitHub repos, PRs, code search                    |
| `playwright`       | UI/browser testing                                |
| `supabase`         | GBrain DB, Supabase queries                       |
| `topaz-labs`       | Image/video enhancement (cloud)                   |
| `stitch`           | `/stitch-design` UI generation                    |
| `mongodb`          | MongoDB cluster work                              |
| `blender`          | 3D modeling (Blender + MCP addon must be running) |
| `vocab-translator` | Translation QA pipeline                           |

Remote claude.ai servers (Gmail, Calendar, Canva, etc.) — manage via Settings → Integrations on claude.ai.

## Skill Routing

Invoke via the Skill tool **first** when the request matches.

| Request type                                    | Skill                 |
| ----------------------------------------------- | --------------------- |
| Product ideas, brainstorming, "worth building?" | `office-hours`        |
| Bugs, errors, 500s, "why broken?"               | `investigate`         |
| Ship / deploy / create PR                       | `ship`                |
| QA, find bugs, test the site                    | `qa`                  |
| Code review                                     | `review`              |
| Update docs after shipping                      | `document-release`    |
| Design system, brand                            | `design-consultation` |
| Visual audit, design polish                     | `design-review`       |
| Architecture review                             | `plan-eng-review`     |
| New Dragonsuite service                         | `dragonsuite-add`     |

## GBrain

- Engine: postgres (Supabase — project zvkwushxufacojfbmppq, us-east-1)
- Config: `~/.gbrain/config.json` (mode 0600), MCP registered user scope (`gbrain serve`)
- Cross-machine restore: copy `~/.gstack-brain-remote.txt` to new machine, run `gstack-brain-restore`
