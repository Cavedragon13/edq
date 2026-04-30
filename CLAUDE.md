# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a personal AI development environment focused on video generation, vision AI, image generation, and LLM experimentation. The repository contains scripts and launchers for various AI models including Wan2GP (video generation), DragonFlux Klein (image generation), and Dragonsight 4.5 (vision AI).

## Directory Structure

```
/srv/containers/edq/
├── .env                # API keys (NEVER duplicate - single source of truth)
├── .mcp.json           # MCP server config (NEVER duplicate)
├── CLAUDE.md           # This file - project documentation
├── config/             # Configuration files (dragonsuite.json)
├── docs/               # Documentation (setup guides, service docs)
│   ├── services/       # Detailed service documentation
│   ├── venvs.md        # Virtual environment registry
│   └── organization-principles.md  # Organization rules (avoid duplicates)
├── scripts/            # Standalone Python scripts and shell launchers
├── projects/           # Cloned AI project repositories (self-contained)
├── models/             # Downloaded AI models and weights
├── media/              # Media files, HTML apps
├── mcp-servers/        # Custom MCP server implementations
├── pinokio/            # Pinokio launcher system
├── venv_*/             # Virtual environments at top level
├── cache_huggingface/  # HF hub cache (symlinked from ~/.cache/huggingface)
└── lmstudio/           # LM Studio data (symlinked from ~/.lmstudio)
```

**Organization Principle:** Single source of truth - no duplicates. Use symlinks when files must exist in multiple locations. See [docs/organization-principles.md](docs/organization-principles.md) for details.

## Port Layout

| Port  | Service               | Type               | Documentation                                           |
| ----- | --------------------- | ------------------ | ------------------------------------------------------- |
| 1234  | LM Studio API         | On-demand (manual) | -                                                       |
| 8080  | Dragonsight 4.5       | On-demand (GPU)    | [Vision AI](docs/services/vision-ai.md)                 |
| 8100  | Dragonsuite Dashboard | On-demand          | Central launcher                                        |
| 8001  | DragonFlux Klein      | On-demand (GPU)    | [Image Generation](docs/services/image-generation.md)   |
| 8002  | Wan2GP                | On-demand (GPU)    | [Video & Music](docs/services/video-music.md)           |
| 8003  | Fish Speech S2-Pro    | On-demand (GPU)    | [Audio & TTS](docs/services/audio-tts.md)               |
| 8004  | HeartMuLa             | On-demand (GPU)    | [Video & Music](docs/services/video-music.md)           |
| 8005  | SAM 2.1               | On-demand (GPU)    | [Vision AI](docs/services/vision-ai.md)                 |
| 8006  | LivePortrait          | On-demand (GPU)    | [Vision AI](docs/services/vision-ai.md)                 |
| 8007  | Hunyuan3D-2           | On-demand (GPU)    | [Utilities](docs/services/utilities.md)                 |
| 8009  | Qwen3-TTS             | On-demand (GPU)    | [Audio & TTS](docs/services/audio-tts.md)               |
| 8010  | Real-ESRGAN           | On-demand (GPU)    | [Image Generation](docs/services/image-generation.md)   |
| 8011  | Z-Image Base          | On-demand (GPU)    | [Image Generation](docs/services/image-generation.md)   |
| 8012  | Rembg                 | On-demand (GPU)    | [Image Generation](docs/services/image-generation.md)   |
| 8013  | Qwen-Image-Layered    | On-demand (GPU)    | [Image Generation](docs/services/image-generation.md)   |
| 8014  | Qwen3-Audiobook       | On-demand          | [Audio & TTS](docs/services/audio-tts.md)               |
| 8015  | Dragonart Studio      | Production         | [Utilities](docs/services/utilities.md)                 |
| 8016  | LTX-2 (19B)           | On-demand (GPU)    | T2V via LTX2Pipeline, sequential CPU offload            |
| 8020  | MCP Inspector         | On-demand          | [Utilities](docs/services/utilities.md)                 |
| 8021  | ACE-Step 1.5          | On-demand (GPU)    | [Video & Music](docs/services/video-music.md)           |
| 8025  | Dolphin Vision 7B     | On-demand (GPU)    | Uncensored VLM image Q&A                                |
| 8026  | Audio Workstation     | On-demand (GPU)    | Enhance+48kHz · Stems · Dereverb · ASR · /editor/       |
| 8028  | LTX-Video 0.9.8-13B   | On-demand (GPU)    | Standalone T2V+I2V, 7-step distilled, 3-pass upscale    |
| 8029  | Dragonsong            | On-demand          | Lyria RealTime music - live prompt steering, record     |
| 8030  | Horse Racing v2       | On-demand          | Win/Place/Show betting, parlay tickets, AI opponents    |
| 8031  | Interactive Games     | On-demand          | Survival Series, Lunar Reckoning, text adventures       |
| 8032  | M.U.L.E.              | On-demand          | Economic strategy game, tribute to Dani Bunten Berry    |
| 8033  | Concert Shirt         | On-demand          | Ticket OCR → concert list → print-on-demand shirt       |
| 8034  | _(retired)_           | —                  | Merged into Audio Workstation (8026)                    |
| 8035  | The Movies            | On-demand          | AI film studio — Nano Banana 2 + Veo 3.1 + Lyria 3      |
| 8037  | TADA TTS              | On-demand (GPU)    | Hume AI voice cloning, 9 languages (TADA-3B-ML)         |
| 8038  | MatAnyone 2           | On-demand (GPU)    | Human video matting, click-to-select, alpha output      |
| 8039  | Linkding              | On-demand          | Cross-browser bookmark manager (Docker)                 |
| **minidragon services (192.168.7.114)** | | | |
| 8096  | Jellyfin              | Always-on (minidragon) | Movie/TV/music/photo server, Intel QSV transcode    |
| 2283  | Immich                | Always-on (minidragon) | Photo/video library, face recognition, external lib |
| 4533  | Navidrome             | Always-on (minidragon) | Music streaming, FLAC-native, Subsonic API          |
| 25600 | Komga                 | Always-on (minidragon) | Comics/ebooks — CBR/CBZ/EPUB/PDF                    |
| 9000  | Portainer             | Always-on (minidragon) | Docker management UI for minidragon + udragon       |
| 8040  | DragonGlass           | On-demand          | Google Maps scout + live Street View + Gemini transform |
| 8060  | Downloads Gallery     | On-demand          | Image + video gallery, slideshow, lightbox, delete      |
| 8041  | AI Toolkit            | On-demand (GPU)    | LoRA trainer for FLUX — upload images, caption, train   |
| 8042  | Voxtral TTS           | On-demand (GPU)    | Mistral Voxtral-4B-TTS-2603, 20 voices, 9 languages     |
| 8043  | Gemma 4 E4B           | On-demand          | Chat UI over local Ollama, 128K ctx, multimodal         |
| 8044  | Agentic Video Editor  | On-demand (GPU)    | 4-agent pipeline — Director, Trim, Editor, Reviewer     |
| 8045  | _(retired)_           | —                  | Superseded by OmniVoice Studio (8051)                   |
| 8046  | Dragonweyr            | On-demand          | Polymarket scout + Claude AI analysis + CLOB execution  |
| 8051  | OmniVoice Studio      | On-demand (GPU)    | Cinematic dubbing — transcribe, translate, re-voice     |
| 8047  | Dragonweyr-Kalshi     | On-demand          | Kalshi scout + Claude AI analysis + order execution     |
| 8048  | Trading Dashboard     | On-demand          | Paper trading dashboard (trading_dashboard.py)          |
| 8049  | VoxCPM2               | On-demand (GPU)    | 2B diffusion TTS, 48kHz, 30+ languages, voice clone     |
| 8050  | Unsloth Studio        | On-demand (GPU)    | LLM fine-tuning - LoRA/QLoRA/RL, dataset creator        |
| 8888  | Jupyter (reserved)    | Future             | -                                                       |
| 11434 | Ollama API            | Always-on (snap)   | -                                                       |

## Service Quick Reference

### Core Services

**Dragonsuite Dashboard** (port 8100)

- Central launcher hub for all services
- Status monitoring, QR codes, git revision info
- **Launch:** `bash scripts/start_dragonsuite.sh`

**Dragonsight 4.5** (port 8080) - [Full docs](docs/services/vision-ai.md)

- Vision AI: Ollama (qwen3-vl:8b, llama3.2-vision:11b), Florence-2 (local), Gemini, LM Studio, Dolphin
- Drag-and-drop image analysis, smart file naming
- **Launch:** `bash scripts/start_dragonsight.sh`

### Image Generation - [Full docs](docs/services/image-generation.md)

- **DragonFlux Klein** (8001) - FLUX.2-klein (fast) + FLUX.1-dev HD Mode with LoRA support
- **Z-Image Base + Turbo** (8011) - Alibaba's 6B text-to-image (Base/Turbo/Fast modes)
- **Qwen-Image-Layered** (8013) - Layer decomposition for editing
- **Real-ESRGAN** (8010) - AI upscaling with multiple models

### Video & Music - [Full docs](docs/services/video-music.md)

- **Wan2GP** (8002) - Video generation (Wan 2.0)
- **LTX-2 (19B)** (8016) - T2V via LTX2Pipeline, sequential CPU offload, diffusers
- **LTX-Video 0.9.8-13B** (8028) - 7-step distilled T2V+I2V with 3-pass upscale, diffusers
- **HeartMuLa** (8004) - Music generation from lyrics (~12GB VRAM)
- **ACE-Step 1.5** (8021) - Ultra-fast music generation (<4GB VRAM)

### Audio & TTS - [Full docs](docs/services/audio-tts.md)

- **Fish Speech** (8003) - Expressive TTS with voice cloning
- **Qwen3-TTS** (8009) - High-quality TTS with voice design
- **Qwen3-Audiobook** (8014) - Document to audiobook conversion
- **Audio Workstation** (8026) - Enhance+48kHz (LavaSR) · Stem separation · Dereverb · ASR (EN/ZH/YUE) · Waveform editor at /editor/

### Vision AI - [Full docs](docs/services/vision-ai.md)

- **SAM 2.1** (8005) - Image/video segmentation
- **LivePortrait** (8006) - Portrait animation with expression transfer
- **Dolphin Vision 7B** (8025) - Uncensored VLM for unrestricted image Q&A

### Utilities - [Full docs](docs/services/utilities.md)

- **Hunyuan3D-2** (8007) - Image to 3D mesh generation
- **MCP Inspector** (8020) - Security auditing for MCP servers
- **Dragonart Studio** (8015) - 70+ AI image transformation modes (React app)
- **Topaz Labs AI** (MCP-only, no port) - Cloud image enhancement, 21 verified models. Ask Claude to enhance; uses `topaz_enhance_image` / `topaz_enhance_generative` tools. GitHub: [Cavedragon13/topaz-labs-mcp](https://github.com/Cavedragon13/topaz-labs-mcp)
- **Pinokio** - Cross-platform launcher framework

## Common Development Tasks

### Working with the Dashboard

**Launch:**

```bash
cd /srv/containers/edq
bash scripts/start_dragonsuite.sh
```

**Access at:** `http://192.168.7.226:8100`

From here you can start/stop all other services.

### Launching Services

All services follow the same pattern:

```bash
cd /srv/containers/edq
bash scripts/start_<service>.sh
```

Access via: `http://192.168.7.226:<port>`

See service documentation for detailed usage:

- [Vision AI Services](docs/services/vision-ai.md)
- [Image Generation Services](docs/services/image-generation.md)
- [Video & Music Generation](docs/services/video-music.md)
- [Audio & TTS Services](docs/services/audio-tts.md)
- [Utility Services](docs/services/utilities.md)

## Architecture Patterns

For detailed technical patterns, see [Architecture Patterns Documentation](docs/architecture-patterns.md):

- Python Script Structure
- Server Launching Pattern
- Video Processing Pattern
- CORS Proxy Pattern (for Local APIs)
- Memory Optimization for Large Models (16GB VRAM)
- React State Management Pattern (Dragonart Studio)

## API Keys & Environment Variables

**Central .env file**: `/srv/containers/edq/.env`

This file contains API keys for external services. **Always use this file** when writing code that needs API access.

### Available Keys

- `OPENAI_API_KEY` - OpenAI API access
- `GOOGLE_API_KEY` - Google API access
- `ANTHROPIC_API_KEY` - Anthropic/Claude API access
- `POE_API_KEY` - Poe.com API access

### Usage in Python

```python
from dotenv import load_dotenv
import os

load_dotenv('/srv/containers/edq/.env')
openai_key = os.getenv('OPENAI_API_KEY')
google_key = os.getenv('GOOGLE_API_KEY')
```

### Usage in Bash/Shell Scripts

```bash
source /srv/containers/edq/.env
# Keys are now available as $OPENAI_API_KEY, $GOOGLE_API_KEY
```

### Usage in Node.js

```javascript
require("dotenv").config({ path: "/srv/containers/edq/.env" });
const openaiKey = process.env.OPENAI_API_KEY;
const googleKey = process.env.GOOGLE_API_KEY;
```

**Note**: The .env file is automatically loaded in bash sessions via `~/.bashrc`.

### API Key Security Rule — Browser vs Server

**Python servers and scripts** (Gradio, FastAPI, shell scripts): load keys from `.env` directly and call external APIs from the server process. Keys never reach the browser. This is safe by default — no extra steps needed.

**Browser JavaScript/TypeScript** (React SPAs, vanilla JS apps): keys baked into a JS bundle can be read by anyone with DevTools, even on LAN. **Never inject an external API key into a browser bundle.** Instead, the local Python server (already present for every Dragonsuite service) must proxy the external API call:

```text
Browser JS  →  /api/proxy-endpoint  →  Python server  →  external API (key from .env)
```

DragonArt Studio is the only current example requiring this pattern (Gemini + OpenAI calls). All other services are Python-based and safe by default.

**Checklist when building a new service with external API calls:**

- Python/Gradio/FastAPI server → ✅ load key from `.env`, call API directly
- Browser SPA → ⚠️ add a proxy endpoint to the Python server, call that instead
- Local API (Ollama, LM Studio) → ✅ no key, no action needed

**Google API project note**: All Google API keys in `.env` come from the **'vscode'** Google Cloud project. When enabling a new Google API, enable it in that project.

## Environment Details

- **Platform**: Linux (6.17.0-14-generic)
- **Working Directory**: `/srv/containers/edq`
- **Not a Git Repo**: This is a container/workspace, not version controlled
- **User**: edq

### Network Shares (SMB/Samba)

- **[downloads]** - `/home/edq/Downloads` (ai_generated files, temp downloads)
- **[ai_media]** - `/home/edq/ai_generated` (output from all AI services)
- **[knowledge-base]** - `/home/edq/knowledge-base` (Obsidian vault with Dragonsuite docs)
  - Symlink following enabled (`wide links = yes`)
  - Mac/LAN access: `smb://192.168.7.226/knowledge-base`
  - Read/write access for user `edq`

## Important Notes

### Pinokio Development

- **ALWAYS** check `.cursorrules` before modifying Pinokio scripts
- **ALWAYS** reference examples in `system/examples/`
- **ALWAYS** use relative paths in `shell.run` commands
- **NEVER** make assumptions about API syntax - check `PINOKIO.md`
- Check logs first when debugging (`logs/api/latest` or `pinokio/logs/api/latest`)

See [Utilities Documentation](docs/services/utilities.md#pinokio-launcher-system) for details.

### Model Backend Selection

- **Ollama**: Better for local deployment, easier setup
- **LM Studio**: OpenAI-compatible API, good for uncensored models
- Scripts often support both via backend selector

### Hardware Constraints

- **GPU**: RTX 5070 Ti with 16GB VRAM
- **Architecture**: Blackwell (sm_120 / CUDA compute capability 12.0)
- **PyTorch requirement**: Must use CUDA 12.8 builds (`--index-url https://download.pytorch.org/whl/cu128`)
  - Standard PyTorch releases (cu124, cu126) do NOT support Blackwell
  - Always check working venvs for correct versions before creating new ones
- Large models (14B+) require heavy optimization or cloud alternatives
- Scripts include fallbacks and cloud service options

### Cloud/Remote Fallbacks (via MCP)

When local GPU is occupied, these Hugging Face Spaces are available via Claude Code MCP tools:

| Task               | Space                                   | Notes                             |
| ------------------ | --------------------------------------- | --------------------------------- |
| Image Generation   | `mcp-tools/Qwen-Image-Fast`             | High quality, good text rendering |
| Image Editing      | `mcp-tools/FLUX.1-Kontext-Dev`          | Edit images with prompts          |
| Video Generation   | `mcp-tools/wan2-2-fp8da-aoti-faster`    | Image-to-video                    |
| Background Removal | `not-lain/background-removal`           | Quick background removal          |
| OCR                | `mcp-tools/DeepSeek-OCR-experimental`   | Extract text from images          |
| TTS                | `ResembleAI/Chatterbox`                 | Voice cloning TTS                 |
| Segmentation       | `prithivMLmods/SAM3-Image-Segmentation` | Object detection/masking          |

Use `dynamic_space` tool with `operation: "view_parameters"` to inspect before invoking.

### PyTorch Installation Template

When creating new venvs that need PyTorch + CUDA:

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
```

### File Paths

- Use `Path.home()` or `os.path.expanduser("~")` for home directory
- Scripts assume running from `/srv/containers/edq`
- Virtual environments: `/srv/containers/edq/venv_<project>` (see `docs/venvs.md`)

## Code Style

- Python scripts use type hints minimally
- Gradio interfaces favor functional over OOP
- Shell scripts use bash with `set -e` for strict error handling
- JavaScript (Pinokio) uses module.exports, template expressions `{{...}}`
- Clear user-facing messages with emoji (🚀, ✓, ❌, etc.)

### Parallel Execution

**Whenever you need to perform multiple independent operations, invoke all relevant tools simultaneously rather than sequentially.**

- Reading multiple files → use multiple Read tool calls in one message
- Searching different patterns → use multiple Grep calls in parallel
- Running independent bash commands → use multiple Bash tool calls
- **Benefits:** Faster execution, no waiting between operations
- **Don't parallelize:** Operations with dependencies or sequential state changes

See [Development Best Practices](docs/organization-principles.md#development-best-practices) for detailed examples.

### Syntax-Check Before Declaring Done (SOP — 2026-03-02)

**ALWAYS run a syntax check on every code file before saying it's ready.** Visual review misses things like unescaped apostrophes in JS strings and backslash escapes inside Python f-string expressions.

```bash
# Python
python3 -m py_compile scripts/my_script.py

# HTML — check all embedded <script> blocks
python3 -c "
import re, sys
src = open('media/my_app.html').read()
blocks = re.findall(r'<script[^>]*>(.*?)</script>', src, re.DOTALL)
for i, b in enumerate(blocks):
    try:
        compile(b, f'block_{i}', 'exec')
    except SyntaxError as e:
        print(f'Block {i}: {e}')
        sys.exit(1)
print('OK')
" && node -e "
const fs = require('fs');
const src = fs.readFileSync('media/my_app.html', 'utf8');
const blocks = [...src.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)].map(m=>m[1]);
blocks.forEach((b,i)=>{try{new Function(b)}catch(e){console.error('Block '+i+':',e.message);process.exit(1)}});
console.log('JS OK');
"

# Standalone JS
node --check file.js
```

Common traps caught by this check:

- `'That's a wrap!'` — unescaped apostrophe in single-quoted JS string → breaks entire `<script>` block
- `f"path/{datetime.now().strftime(\"%Y%m%d\")}"` — backslash escape in f-string expression → invalid Python 3.12+

## Web Development Standards

### Dark Mode Requirements

**CRITICAL**: When coding for the web (HTML/CSS/JavaScript), **ALWAYS** include:

1. **Dark mode toggle** - Circular button with moon/sun icon (🌙/☀️)
   - Position: Top-right corner of header
   - Smooth transitions (0.3s ease) on all theme-affected elements
   - Hover effect: rotate(180deg)

2. **Default to dark mode** - Dark theme should be the default state on first load

3. **Persistent preference** - Use `localStorage` to remember user's choice:

   ```javascript
   localStorage.setItem("app-theme", isDark ? "dark" : "light");
   ```

4. **Complete coverage** - Theme must affect:
   - Body background (gradients preferred)
   - Container backgrounds
   - All text colors (ensure proper contrast)
   - Input fields, textareas, selects
   - Buttons (use muted colors in dark mode)
   - Borders and dividers
   - Code blocks and pre-formatted text

5. **Color palette guidelines**:
   - **Dark mode backgrounds**: `#1e1e1e`, `#2d2d2d`, `#1a1a2e`
   - **Dark mode text**: `#e0e0e0`, `#9ca3af`
   - **Dark mode borders**: `#4a5568`, `#374151`
   - **Maintain brand colors** but mute them for dark mode

6. **Implementation pattern**:

   ```css
   body.dark-mode .element {
     /* dark mode styles */
   }
   ```

7. **JavaScript initialization (default to dark)**:
   ```javascript
   const savedTheme = localStorage.getItem("app-theme");
   if (savedTheme === "light") {
     // Only use light mode if explicitly chosen
     themeToggle.textContent = "🌙";
   } else {
     // Default to dark mode
     body.classList.add("dark-mode");
     themeToggle.textContent = "☀️";
     if (!savedTheme) {
       localStorage.setItem("app-theme", "dark");
     }
   }
   ```

### Example Implementation

See `media/dragonsight4.html` for reference implementation with:

- Toggle button in header
- **Defaults to dark mode** on first load
- localStorage persistence
- Smooth transitions
- Complete theme coverage

## Known Issues & Cleanup Tasks

### ✅ Completed Fixes (2026-01-20)

1. **✅ Port standardization**: Moved all Dragonsuite tools to 8xxx ports
2. **✅ Removed legacy components**: Deleted Qwen Vision, LTX-Video, orphaned directories
3. **✅ Created venv registry**: `docs/venvs.md` tracks all virtual environments
4. **✅ Fixed DragonFlux Klein**: Corrected launch script path in config
5. **✅ Updated dashboard config**: `config/dragonsuite.json` reflects current tools

### Venv Management

- All venvs centralized at `/srv/containers/edq/venv_*`
- Registry at `docs/venvs.md` - update when adding/removing projects
- When removing a project: delete venv, update registry, update `config/dragonsuite.json`

### Future Additions (reserved ports)

- 8888: Jupyter Notebook
- Additional tools: assign next available 800x port

## Shorthand Commands

### "update the kb"

When the user says **"update the kb"** (or close variants), perform all of the following:

1. **Update memory files** — review the session and update `~/.claude/projects/-srv-containers-edq/memory/MEMORY.md` and any relevant topic files (`common_issues.md`, `gpu_optimization.md`, `web_ui_patterns.md`, etc.) with new lessons, patterns, or corrections.

2. **Update CLAUDE.md** — if any port assignments, architecture patterns, service names, or project-level facts changed, update this file immediately.

3. **Create or update today's daily note** in Obsidian at `/home/edq/knowledge-base/Daily Notes/YYYY-MM-DD.md` using the template in `Directions/Daily Note Template.md`. The note should include:
   - A 2-3 sentence summary of what the session accomplished
   - Bullet list of what was done
   - Any new lessons learned (beyond what went to memory files)
   - Which meta-files were updated
   - Open items / follow-ups

**Format**: `YYYY-MM-DD.md` using today's date. If the file already exists, append to it rather than overwrite.

Do this thoroughly — this is the persistent record of the work. "No summary provided" and "No new lessons captured" are not acceptable outputs.

---

## Standard Operating Procedures (SOPs)

### Model Downloads - CRITICAL SOP (2026-02-15)

**Rule:** NEVER make the first run of a tool wait for model downloads.

**Instead:**

1. Create standalone download script: `scripts/download_<toolname>_models.sh`
2. Use Python `snapshot_download()` API (resumable, idempotent)
3. Document in setup instructions
4. Add model check to launch script (fail fast if missing)

**Template:**

```bash
#!/bin/bash
source /srv/containers/edq/venv_toolname/bin/activate

python << 'PYEOF'
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id="org/repo",
    local_dir="/srv/containers/edq/models/toolname"
)
PYEOF
```

**Quick Start:** Copy [scripts/template_download_models.sh](scripts/template_download_models.sh) and customize.

**See:** [docs/sop-model-downloads.md](docs/sop-model-downloads.md) for complete guide, examples, and best practices.

**Benefits:**

- ✅ Better UX (instant launches after setup)
- ✅ Resumable downloads (network-safe)
- ✅ Parallel setup (download multiple tools during idle time)
- ✅ Clear separation of concerns

---

## Lessons Learned & Best Practices (2026-02-08)

### Meta-Lesson: Always Try Simple/Local Solutions First

Before suggesting paid APIs, cloud services, or complex architectures, ask: "Can this be done locally with basic file operations?"

Example: Conversation analysis task

- ❌ Initial approach: Use Claude API ($5-10) to analyze conversations
- ✅ Better approach: Export to markdown (free), read locally (free), synthesize (free)
- **Result**: Same quality, $0 cost

### Key Anti-Patterns to Avoid

1. **Overthinking solutions** - Reaching for external services when local tools work
2. **Hardcoding IP addresses** - Use auto-detection or localhost/0.0.0.0
3. **Ignoring venv documentation** - Always update `docs/venvs.md`
4. **Using Gradio for everything** - Switch to HTML/JS when clipboard operations or custom interactions needed
5. **Assuming model censorship is OK** - Always offer uncensored alternatives (LM Studio + Dolphin)
6. **Adding unrequested features** - Do exactly what's requested, offer enhancements separately
7. **Asking the user to run terminal commands** - Use the Bash tool directly. Never say "run this command and paste the output" — just run it. The user should not be doing work that Claude Code can do. This ranks alongside RTFM as a core behavioral rule.

### Most Common Recurring Issues

1. **CUDA OOM errors** - Add `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` to launcher
2. **Dark mode requested** - User asks for this immediately on every new web UI
3. **Clipboard operations broken** - Gradio limitations, need paste button + one-click copy
4. **LM Studio connection fails** - CORS issues, use 127.0.0.1 proxy pattern
5. **Multiple GPU services conflict** - Only run one GPU-heavy service at a time
6. **Remotion caching issues** - Changes not reflected, need hard refresh + cache clear
7. **Documentation drift** - Update CLAUDE.md and venvs.md IMMEDIATELY after changes

**See also:**

- Full analysis: `~/claude_conversations_review/LESSONS_LEARNED.md`
- Critical lessons: `~/.claude/projects/-srv-containers-edq/memory/MEMORY.md`
- [Architecture Patterns](docs/architecture-patterns.md) for technical details

### Memory Organization Pattern (Best Practice)

**Problem:** Claude Code's auto memory has a 200-line limit. How to preserve more context?

**Solution:** Use MEMORY.md as an **index** that references detailed topic files.

**Structure:**

```
~/.claude/projects/-srv-containers-edq/memory/
├── MEMORY.md                  # <200 lines, auto-loaded, quick reference
├── gpu_optimization.md        # Detailed GPU/CUDA lessons
├── web_ui_patterns.md         # Comprehensive web UI standards
├── common_issues.md           # Troubleshooting guide
└── [additional topics...]     # As needed
```

**When to use:** When you find yourself hitting the 200-line limit or when topics are complex enough to deserve their own files.

### Image Generation Best Practices

**Social Media Assets:**

- og-preview.png standard: 1200×630px
- Closest diffusion-compatible: 1200×640px (divisible by 16)
- Use Z-Image Base for text rendering (better than FLUX for readable text)

**Calling Local Gradio APIs Programmatically:**

```python
from gradio_client import Client

# Connect to local service
client = Client("http://127.0.0.1:8011/")

# Call API endpoint
result = client.predict(
    prompt="your prompt",
    width=1200,
    height=640,  # Must be divisible by 16 for diffusion models
    guidance_scale=7.5,
    num_inference_steps=30,
    api_name="/generate_image"
)

# Result is typically (image_path, status_message)
image_path = result[0]
```

**Key Requirements:**

- Dimensions must be divisible by 16 for diffusion models (e.g., 640 not 630)
- Use `127.0.0.1` not external IP for local services
- Check service is running first (see port list)

---

**Last Updated**: 2026-02-11
**Services**: 20+ AI tools across vision, image, video, audio, and utilities
**Documentation**: Reorganized into topic-specific guides (2026-02-11)

## Skill routing

When the user's request matches an available skill, ALWAYS invoke it using the Skill
tool as your FIRST action. Do NOT answer directly, do NOT use other tools first.
The skill has specialized workflows that produce better results than ad-hoc answers.

Key routing rules:
- Product ideas, "is this worth building", brainstorming → invoke office-hours
- Bugs, errors, "why is this broken", 500 errors → invoke investigate
- Ship, deploy, push, create PR → invoke ship
- QA, test the site, find bugs → invoke qa
- Code review, check my diff → invoke review
- Update docs after shipping → invoke document-release
- Weekly retro → invoke retro
- Design system, brand → invoke design-consultation
- Visual audit, design polish → invoke design-review
- Architecture review → invoke plan-eng-review
- Save progress, checkpoint, resume → invoke checkpoint
- Code quality, health check → invoke health
