# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a personal AI development environment focused on video generation, vision AI, image generation, and LLM experimentation. The repository contains scripts and launchers for various AI models including Wan2GP (video generation), DragonFlux Klein (image generation), and Dragonsight 4 (vision AI).

## Directory Structure

```
/srv/containers/edq/
├── apps/               # Application binaries (LM Studio, Pinokio)
├── config/             # Configuration files (dragonsuite.json)
├── docs/               # Documentation (setup guides, venvs.md registry)
├── scripts/            # Standalone Python scripts and shell launchers
├── projects/           # Cloned AI project repositories
│   ├── Wan2GP/         # Wan2GP video generation
│   ├── wan-animate/    # Wan2.2-Animate-14B project
│   ├── fish-speech/    # Fish Speech TTS
│   ├── heartmula/      # HeartMuLa music generation
│   ├── qwen3-tts/      # Qwen3-TTS (TTS, cloning, voice design)
│   ├── sam2/           # SAM 2.1 segmentation
│   ├── LivePortrait/   # Portrait animation (KlingTeam)
│   ├── hunyuan3d/      # Image to 3D generation
│   └── llama.cpp/      # llama.cpp for GGUF models
├── models/             # Downloaded AI models and weights
├── media/              # Media files, HTML apps (dragonsight4.html, dragonsuite.html)
├── pinokio/            # Pinokio launcher system
├── venv_dragonsuite/   # Dashboard backend venv
├── venv_fish_speech/   # Fish Speech TTS venv
├── venv_florence2/     # Florence2 vision service venv
├── venv_flux2/         # DragonFlux Klein venv
├── venv_heartmula/     # HeartMuLa music venv
├── venv_qwen3_tts/     # Qwen3-TTS venv
├── venv_hunyuan3d/     # Hunyuan3D-2 venv
├── venv_liveportrait/  # LivePortrait venv
├── venv_realesrgan/    # Real-ESRGAN upscaler venv
├── venv_sam2/          # SAM 2.1 venv
├── venv_wan2gp/        # Wan2GP venv
├── venv_zimage/        # Z-Image Base venv
├── venv_rembg/         # Rembg background removal venv
└── venv_qwen_image_layered/  # Qwen-Image-Layered venv
```

## Port Layout

| Port | Service | Type |
|------|---------|------|
| 1234 | LM Studio API | On-demand (manual) |
| 8080 | Dragonsight 4 | Static file server |
| 8100 | Dragonsuite Dashboard | On-demand |
| 8001 | DragonFlux Klein | On-demand (GPU) |
| 8002 | Wan2GP | On-demand (GPU) |
| 8003 | Fish Speech | On-demand (GPU) |
| 8004 | HeartMuLa | On-demand (GPU) |
| 8005 | SAM 2.1 | On-demand (GPU) |
| 8006 | LivePortrait | On-demand (GPU) |
| 8007 | Hunyuan3D-2 | On-demand (GPU) |
| 8009 | Qwen3-TTS | On-demand (GPU) |
| 8010 | Real-ESRGAN | On-demand (GPU) |
| 8011 | Z-Image Base | On-demand (GPU) |
| 8012 | Rembg | On-demand (GPU) |
| 8013 | Qwen-Image-Layered | On-demand (GPU) |
| 8014 | Qwen3-Audiobook | On-demand |
| 8888 | Jupyter (reserved) | Future |
| 11434 | Ollama API | Always-on (snap) |

## Key Components

### 1. Dragonsuite Dashboard
- **HTML App**: `media/dragonsuite.html`
- **Backend**: `scripts/dragonsuite_server.py`
- **Launcher**: `scripts/start_dragonsuite.sh`
- **Port**: 8100
- **Purpose**: Central launcher hub for all Dragonsuite tools
- **Features**:
  - Shows service status (running/stopped)
  - Start/Stop buttons for each tool
  - QR codes for mobile access
  - Git revision info for projects
- **Web UI**: `http://192.168.7.226:8100`
- **Config**: `config/dragonsuite.json`

### 2. Dragonsight 4 (Vision AI)
- **HTML App**: `media/dragonsight4.html`
- **Launcher**: `scripts/start_dragonsight.sh`
- **Port**: 8080
- **Purpose**: Drag-and-drop image analysis, AI descriptions, smart file naming
- **Primary Backend**: Ollama (always-on via snap)
  - `qwen3-vl:8b` (default, 6.1GB)
  - `llama3.2-vision:11b` (optional, 7.8GB)
- **Secondary Backend**: LM Studio (manual start)
  - GLM-4.6V with Dolphin uncensored prompt
- **Features**:
  - Pure frontend (HTML/JS) - no Python backend needed
  - Model selector for Ollama VLMs
  - Automatic fallback between backends
  - Clipboard paste support (Ctrl+V)
  - Parallel API calls for faster results
  - Copy buttons for all outputs
  - Metadata JSON download
- **Backend URLs** (via proxy to avoid CORS):
  - Ollama: `http://127.0.0.1:8080/api/ollama/generate` → proxied to `127.0.0.1:11434`
  - LM Studio: `http://localhost:1234/v1/chat/completions` (direct, same-origin not needed)
- **Web UI**: `http://192.168.7.226:8080`
- **Architecture**: Frontend served on 8080, Ollama calls proxied through same port (see Architecture Patterns)

### 3. DragonFlux Klein (Image Generation)
- **Script**: `scripts/flux2_klein_gradio.py`
- **Launcher**: `scripts/start_flux2_klein.sh`
- **Port**: 8001
- **Venv**: `venv_flux2`
- **Purpose**: FLUX.2-klein image generation with LoRA support
- **Features**:
  - LoRA model loading from `~/models/loras/flux-klein/`
  - Output saves to `~/ai_generated/flux2-klein/`
  - Gradio interface
- **Web UI**: `http://192.168.7.226:8001`

### 4. Wan2GP (Video Generation)
- **Location**: `projects/Wan2GP/`
- **Launcher**: `scripts/start_wan2gp.sh`
- **Port**: 8002
- **Venv**: `venv_wan2gp`
- **Purpose**: Wan 2.0 video generation
- **Recommended models** (16GB VRAM):
  - Wan 2.2 Ovi (6GB) - fastest
  - LTX 2 (8GB)
  - Flux 2 int8 (8GB)
- **Web UI**: `http://192.168.7.226:8002`

### 5. HeartMuLa (Music Generation)
- **Location**: `projects/heartmula/`
- **Launcher**: `scripts/start_heartmula.sh`
- **Port**: 8004
- **Venv**: `venv_heartmula`
- **Purpose**: AI music generation from lyrics and style tags (Suno-level quality, open source)
- **Model**: HeartMuLa-oss-3B (Apache 2.0 license)
- **Features**:
  - Lyrics-to-music generation
  - Section structure support ([Verse], [Chorus], [Bridge], etc.)
  - Style tags (instruments, mood, genre, tempo)
  - Adjustable temperature, top-k, CFG scale
  - Output: MP3 files saved to `~/ai_generated/heartmula/`
- **Web UI**: `http://192.168.7.226:8004`
- **Requirements**: ~12GB VRAM, ~10GB disk for models

### 6. Fish Speech (Text-to-Speech)
- **Location**: `projects/fish-speech/`
- **Launcher**: `scripts/start_fish_speech.sh`
- **Port**: 8003
- **Venv**: `venv_fish_speech`
- **Purpose**: Expressive TTS with voice cloning (OpenAudio S1-mini, 0.5B params)
- **Features**:
  - Zero-shot TTS (no reference audio needed)
  - Voice cloning from 10-30s audio samples
  - Emotion control markers (angry, sad, excited, etc.)
  - Multi-language support (EN, CN, JP, DE, FR, ES, KO, AR, RU, etc.)
  - Gradio web interface
- **Web UI**: `http://192.168.7.226:8003`
- **Requirements**: 12GB VRAM

### 7. Qwen3-TTS (Text-to-Speech)
- **Location**: `projects/qwen3-tts/`
- **Launcher**: `scripts/start_qwen3_tts.sh`
- **Port**: 8009
- **Venv**: `venv_qwen3_tts`
- **Purpose**: High-quality TTS with voice cloning and voice design
- **Models**: Qwen3-TTS-12Hz-1.7B (Base, CustomVoice, VoiceDesign)
- **Features**:
  - TTS with 9 predefined speakers + style control
  - Voice cloning from reference audio
  - Voice design from natural language descriptions
  - Multi-language support (EN, CN, JP, KO, FR, DE, ES, PT, RU)
  - Lazy model loading (one model at a time)
- **Web UI**: `http://192.168.7.226:8009`
- **Requirements**: ~6-8GB VRAM per model (with FlashAttention)
- **Tip**: Switching tabs may reload models as only one is loaded at a time

### 8. SAM 2.1 (Segment Anything)
- **Location**: `projects/sam2/`
- **Launcher**: `scripts/start_sam2.sh`
- **Port**: 8005
- **Venv**: `venv_sam2`
- **Purpose**: Meta's foundation model for image and video segmentation
- **Features**:
  - Click-to-segment in images
  - Track objects across video frames
  - Automatic mask generation
  - Point and box prompts
- **Web UI**: `http://192.168.7.226:8005`
- **Requirements**: ~6GB VRAM

### 9. LivePortrait (Portrait Animation)
- **Location**: `projects/LivePortrait/`
- **Launcher**: `scripts/start_liveportrait.sh`
- **Port**: 8006
- **Venv**: `venv_liveportrait`
- **Purpose**: KlingTeam's portrait animation with expression transfer
- **Features**:
  - Image to animated portrait
  - Video-driven face animation
  - Expression transfer from driving video
  - Animals mode (cats & dogs)
- **Web UI**: `http://192.168.7.226:8006`
- **Requirements**: ~6GB VRAM
- **Tip**: Use short driving videos (2-5s) for best results

### 10. Hunyuan3D-2 (Image to 3D)
- **Location**: `projects/hunyuan3d/`
- **Launcher**: `scripts/start_hunyuan3d.sh`
- **Port**: 8007
- **Venv**: `venv_hunyuan3d`
- **Purpose**: Tencent's image-to-3D model generation
- **Features**:
  - Image to 3D mesh
  - Texture synthesis
  - GLB/OBJ export
- **Web UI**: `http://192.168.7.226:8007`
- **Requirements**: ~6GB VRAM (shape), ~16GB (with texture)

### 11. Real-ESRGAN (Image Upscaling)
- **Script**: `scripts/realesrgan_gradio.py`
- **Launcher**: `scripts/start_realesrgan.sh`
- **Port**: 8010
- **Venv**: `venv_realesrgan`
- **Purpose**: AI image upscaling with multiple models
- **Models**:
  - RealESRGAN_x4plus - General photos (default)
  - RealESRGAN_x4plus_anime_6B - Anime/illustration
  - RealESRGAN_x2plus - 2x upscaling (faster)
  - realesr-general-x4v3 - Compact with denoise
- **Features**:
  - Up to 8x output scaling
  - Face enhancement (GFPGAN)
  - Tiling for large images
  - Clipboard paste support
- **Web UI**: `http://192.168.7.226:8010`
- **Requirements**: ~4GB VRAM
- **Output**: `~/ai_generated/realesrgan/`

### 13. Z-Image Base (Text-to-Image)
- **Script**: `scripts/zimage_base_gradio.py`
- **Launcher**: `scripts/start_zimage.sh`
- **Port**: 8011
- **Venv**: `venv_zimage`
- **Purpose**: Alibaba Tongyi's 6B parameter text-to-image model
- **Model**: Tongyi-MAI/Z-Image (Apache 2.0 license)
- **Features**:
  - CFG scale control (unlike Turbo variant)
  - Negative prompt support
  - Superior photorealism, hands, text rendering
  - LoRA support from `~/models/loras/zimage/`
  - Multiple aspect ratio presets
- **Web UI**: `http://192.168.7.226:8011`
- **Requirements**: ~13-14GB VRAM (bf16)
- **Output**: `~/ai_generated/zimage/`
- **Tips**: CFG 7-10 recommended, 30 steps for quality

### 14. Qwen-Image-Layered (Layer Decomposition)
- **Script**: `scripts/qwen_image_layered_gradio.py`
- **Launcher**: `scripts/start_qwen_image_layered.sh`
- **Port**: 8013
- **Venv**: `venv_qwen_image_layered`
- **Purpose**: Decompose images into multiple RGBA layers for advanced editing
- **Model**: Qwen/Qwen-Image-Layered (Apache 2.0 license)
- **Features**:
  - Variable layer count (2-8 layers)
  - RGBA PNG export for each layer
  - ZIP download of all layers
  - PPTX export for presentations
  - Recursive decomposition possible
- **Web UI**: `http://192.168.7.226:8013`
- **Requirements**: ~14-16GB VRAM (uses CPU offloading)
- **Output**: `~/ai_generated/qwen-layered/`
- **Tips**: Close other GPU services before use; 640px resolution recommended

### 15. Qwen3-Audiobook (Document to Audiobook)
- **Script**: `scripts/qwen3_audiobook_gradio.py`
- **Launcher**: `scripts/start_qwen3_audiobook.sh`
- **Port**: 8014
- **Venv**: Shares `venv_qwen3_tts`
- **Purpose**: Convert documents to MP3 audiobooks using Qwen3-TTS
- **Requires**: Qwen3-TTS running on port 8009
- **Supported Formats**:
  - PDF (text-based)
  - EPUB (e-books)
  - DOCX/DOC (Word documents)
  - TXT (plain text)
- **Features**:
  - 9 predefined speaker voices
  - Custom style instructions
  - Intelligent text chunking (~1200 words)
  - Progress tracking
- **Web UI**: `http://192.168.7.226:8014`
- **Requirements**: CPU only (TTS uses GPU via port 8009)
- **Output**: `~/ai_generated/qwen3-audiobook/`
- **Tips**: Start Qwen3-TTS first before using audiobook converter

### 16. Pinokio Launcher System
- **Location**: `pinokio/`
- **Purpose**: Cross-platform launcher framework for AI apps
- **Important Files**:
  - `.cursorrules`: Contains strict development guidelines (always reference when working with Pinokio)
  - `PINOKIO.md`: Full API documentation
  - `prototype/system/examples/`: Reference examples for all launcher patterns

### 17. Llama.cpp Integration
- **Location**: `projects/llama.cpp/`
- **Purpose**: GGUF model inference for quantized models

## Common Development Tasks

### Working with the Dashboard

**Launch:**
```bash
cd /srv/containers/edq
bash scripts/start_dragonsuite.sh
```

**Access at:** `http://192.168.7.226:8100`

From here you can start/stop all other services.

### Working with Dragonsight 4

**Launch:**
```bash
cd /srv/containers/edq
bash scripts/start_dragonsight.sh
```

**Access at:** `http://192.168.7.226:8080/media/dragonsight4.html`

**Key considerations:**
- **Ollama is always-on** via snap - no manual start needed
- Default model: qwen3-vl:8b, optional: llama3.2-vision:11b
- Pure HTML/JS frontend - no Python dependencies
- LM Studio available as secondary backend (manual start) for uncensored GLM-4.6V

### Working with DragonFlux Klein

**Launch:**
```bash
cd /srv/containers/edq
bash scripts/start_flux2_klein.sh
```

**Access at:** `http://192.168.7.226:8001`

**Key considerations:**
- GPU-heavy (loads FLUX model into VRAM)
- LoRA support via `~/models/loras/flux-klein/`
- Output saves to `~/ai_generated/flux2-klein/`

### Working with Wan2GP

**Launch:**
```bash
cd /srv/containers/edq
bash scripts/start_wan2gp.sh
```

**Access at:** `http://192.168.7.226:8002`

**Key considerations:**
- GPU-heavy, only run one GPU service at a time
- Multiple model options for different VRAM budgets
- Video generation can take several minutes

### Working with Fish Speech

**Launch:**
```bash
cd /srv/containers/edq
bash scripts/start_fish_speech.sh
```

**Access at:** `http://192.168.7.226:8003`

**Key considerations:**
- GPU-heavy (12GB VRAM), only run one GPU service at a time
- First launch downloads ~2GB model weights
- Voice cloning: place 10-30s audio samples in `projects/fish-speech/references/<voice_id>/sample.wav`
- Emotion markers: use `(angry)`, `(excited)`, `(sad)`, etc. in text
- Tone markers: `(whispering)`, `(shouting)`, `(in a hurry tone)`

### Working with HeartMuLa

**Launch:**
```bash
cd /srv/containers/edq
bash scripts/start_heartmula.sh
```

**Access at:** `http://192.168.7.226:8004`

**Key considerations:**
- GPU-heavy (~12GB VRAM), only run one GPU service at a time
- First launch downloads ~10GB of model weights
- Generation speed: ~1x real-time (2 min song = ~2 min generation)
- Output saves to `~/ai_generated/heartmula/`
- Use section tags in lyrics: `[Verse]`, `[Chorus]`, `[Bridge]`, `[Intro]`, `[Outro]`
- Style tags are comma-separated: `piano,happy,uplifting,pop`
- Supports multi-language lyrics

### Working with Qwen3-TTS

**Launch:**
```bash
cd /srv/containers/edq
bash scripts/start_qwen3_tts.sh
```

**Access at:** `http://192.168.7.226:8009`

**Key considerations:**
- GPU-heavy (~6-8GB VRAM per model), only run one GPU service at a time
- First launch downloads ~6GB of model weights (per model type)
- Three modes: TTS (speakers), Voice Clone, Voice Design
- Only one model loaded at a time for 16GB VRAM compatibility
- Switching tabs may reload models
- Output saves to `~/ai_generated/qwen3-tts/`
- 9 predefined speakers: Aiden, Dylan, Eric, Ono_anna, Ryan, Serena, Sohee, Uncle_fu, Vivian
- Voice design: describe age, gender, tone, emotion, accent

### Working with SAM 2.1

**Launch:**
```bash
cd /srv/containers/edq
bash scripts/start_sam2.sh
```

**Access at:** `http://192.168.7.226:8005`

**Key considerations:**
- Click on image to segment objects
- Supports video tracking (propagate mask across frames)
- First launch downloads ~2.5GB checkpoint
- ~6GB VRAM for large model

### Working with LivePortrait

**Launch:**
```bash
cd /srv/containers/edq
bash scripts/start_liveportrait.sh
```

**Access at:** `http://192.168.7.226:8006`

**Key considerations:**
- Upload source portrait + driving video
- First launch downloads ~2GB of model weights
- Use short driving videos (2-5 seconds) for best results
- Animals mode available for cats & dogs
- Expression transfer works best with similar face angles

### Working with Hunyuan3D-2

**Launch:**
```bash
cd /srv/containers/edq
bash scripts/start_hunyuan3d.sh
```

**Access at:** `http://192.168.7.226:8007`

**Key considerations:**
- Upload image → generates 3D mesh
- First launch downloads ~10GB of models
- ~6GB VRAM for shape only, ~16GB for shape + texture
- Exports GLB/OBJ formats

### Working with Real-ESRGAN

**Launch:**
```bash
cd /srv/containers/edq
bash scripts/start_realesrgan.sh
```

**Access at:** `http://192.168.7.226:8010`

**Key considerations:**
- First launch downloads ~200MB of model weights
- ~4GB VRAM for most models
- Use tiling (256/512) for large images to save VRAM
- Face enhancement adds GFPGAN (~500MB additional download)
- Output saves to `~/ai_generated/realesrgan/`
- Anime model works best for illustrations/anime art

### Working with Qwen-Image-Layered

**Launch:**
```bash
cd /srv/containers/edq
bash scripts/start_qwen_image_layered.sh
```

**Access at:** `http://192.168.7.226:8013`

**Key considerations:**
- First launch downloads ~12GB of model weights
- Uses ~14-16GB VRAM with CPU offloading enabled
- Close other GPU services before use
- 640px resolution recommended (1024px uses more VRAM)
- Output saves to `~/ai_generated/qwen-layered/`
- Downloads include ZIP and optional PPTX of all layers

### Working with Qwen3-Audiobook

**Launch:**
```bash
cd /srv/containers/edq
bash scripts/start_qwen3_audiobook.sh
```

**Access at:** `http://192.168.7.226:8014`

**Key considerations:**
- Requires Qwen3-TTS running on port 8009 first
- Start TTS service: `bash scripts/start_qwen3_tts.sh`
- Shares venv with Qwen3-TTS (no separate installation)
- Supports PDF, EPUB, DOCX, DOC, TXT formats
- Text is chunked into ~1200 word segments for reliable TTS
- Output saves to `~/ai_generated/qwen3-audiobook/`
- Long documents may take significant time to convert

### Working with Pinokio Launchers

**Critical workflow (from .cursorrules):**
1. Always reference `.cursorrules` before any Pinokio script changes
2. Check `/home/edq/pinokio/prototype/system/examples` for reference patterns
3. Review `PINOKIO.md` for API syntax
4. Check logs in `logs/` or `pinokio/logs/` for debugging
5. Use relative paths (never absolute) in `shell.run` commands

**Key patterns:**
- Always use `venv` attribute for Python apps
- Capture server URLs with regex patterns like `/(http:\/\/[0-9.:]+)/`
- Set local variables with `local.set` using `{{input.event[1]}}`
- Use `daemon: true` for server launchers
- Prefer `uv` over `pip` for Python package installation

**Project structure:**
```
launcher-root/
├── install.js    # Installation script
├── start.js      # Launch script (daemon: true for servers)
├── reset.js      # Reset dependencies
├── update.js     # Update app and scripts
├── pinokio.js    # UI generator (dynamic menu)
└── pinokio.json  # Metadata
```

## Architecture Patterns

### Python Script Structure
- Most scripts use Gradio for web interfaces
- Scripts typically support multiple backends (Ollama, LM Studio)
- Virtual environments stored alongside projects
- Configuration via constants at top of files
- Subprocess calls for external commands with timeout handling

### Server Launching Pattern
1. Start server with `subprocess.run()` or `shell.run`
2. Capture URL via regex on stdout
3. Set local variable for UI to display
4. Use `daemon: true` to keep process alive

### Video Processing Pattern
For vision models that don't support video:
1. Extract keyframes using OpenCV (`cv2.VideoCapture`)
2. Process each frame individually
3. Combine descriptions/results
4. Clean up temporary frame files

### CORS Proxy Pattern (for Local APIs)
When frontend needs to call a local service that doesn't support CORS (e.g., Ollama):

**Problem**: Browser blocks cross-port requests (8080 → 11434) due to CORS policy.

**Solution**: Proxy through the frontend server to stay same-origin:
```
Frontend (8080) → Server (8080) → Local API (11434)
```

**Implementation** (see `scripts/dragonsight_server.py`):
- Use `BaseHTTPRequestHandler` (not `SimpleHTTPRequestHandler` - breaks POST override)
- Add `Access-Control-Allow-Origin: *` to all responses
- Handle OPTIONS for CORS preflight
- Use `SO_REUSEADDR` to avoid binding errors on restart
- Set adequate timeout (300s for model inference)

**Key rules**:
- **ALWAYS** use `127.0.0.1` for local services, never external IPs
- **DO NOT** use `window.location.hostname` (returns external IP from LAN)
- Test with: `curl -X POST http://127.0.0.1:8080/api/proxy/endpoint`

### Memory Optimization for Large Models (16GB VRAM)

**Environment Variable (REQUIRED in all GPU launcher scripts):**
```bash
# Add before python command in start_*.sh scripts
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
```

Note: `expandable_segments:True` is superior to the older `max_split_size_mb:512` setting.

**CPU Offloading Strategy (for diffusers pipelines):**
```python
# Choose based on VRAM requirements:

# Option 1: Model CPU offload (best speed/memory balance)
# Moves entire models to GPU one at a time
pipeline.enable_model_cpu_offload()

# Option 2: Sequential CPU offload (maximum memory savings, slower)
# Moves individual layers to GPU during forward pass
pipeline.enable_sequential_cpu_offload()

# CRITICAL: Never call .to("cuda") before offloading methods!
```

**VAE Optimizations (always enable for image generation):**
```python
if hasattr(pipeline, 'vae'):
    pipeline.vae.enable_slicing()  # Batch memory reduction
    pipeline.vae.enable_tiling()   # High-res support
```

**Memory Cleanup Pattern:**
```python
import gc
import torch

def clear_gpu_memory():
    """Clear GPU memory between operations."""
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

# Call before inference if VRAM is tight
clear_gpu_memory()
```

**Service VRAM Requirements:**
| Service | VRAM | Offload Strategy |
|---------|------|------------------|
| Qwen-Image-Layered | 14-16GB | Sequential (required) |
| Z-Image Base | 13-14GB | Sequential |
| HeartMuLa | ~12GB | Model |
| Fish Speech | ~12GB | Model |
| Hunyuan3D (shape) | ~6GB | Model |
| SAM 2.1 | ~6GB | Model |
| Real-ESRGAN | ~4GB | None needed |
| LivePortrait | ~6GB | Model |

**General Guidelines:**
- Only run ONE GPU-heavy service at a time
- Use 640px resolution when possible (vs 1024px)
- Limit video length for video generation
- Add user-facing warnings about hardware limits in UI

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
require('dotenv').config({ path: '/srv/containers/edq/.env' });
const openaiKey = process.env.OPENAI_API_KEY;
const googleKey = process.env.GOOGLE_API_KEY;
```

**Note**: The .env file is automatically loaded in bash sessions via `~/.bashrc`.

## Environment Details

- **Platform**: Linux (6.14.0-37-generic)
- **Working Directory**: `/srv/containers/edq`
- **Not a Git Repo**: This is a container/workspace, not version controlled
- **User**: edq
- **Date**: 2026-02-01

## Important Notes

### Pinokio Development
- **ALWAYS** check `.cursorrules` before modifying Pinokio scripts
- **ALWAYS** reference examples in `system/examples/`
- **ALWAYS** use relative paths in `shell.run` commands
- **NEVER** make assumptions about API syntax - check `PINOKIO.md`
- Check logs first when debugging (`logs/api/latest` or `pinokio/logs/api/latest`)

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

| Task | Space | Notes |
|------|-------|-------|
| Image Generation | `mcp-tools/Qwen-Image-Fast` | High quality, good text rendering |
| Image Editing | `mcp-tools/FLUX.1-Kontext-Dev` | Edit images with prompts |
| Video Generation | `mcp-tools/wan2-2-fp8da-aoti-faster` | Image-to-video |
| Background Removal | `not-lain/background-removal` | Quick background removal |
| OCR | `mcp-tools/DeepSeek-OCR-experimental` | Extract text from images |
| TTS | `ResembleAI/Chatterbox` | Voice cloning TTS |
| Segmentation | `prithivMLmods/SAM3-Image-Segmentation` | Object detection/masking |

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
   localStorage.setItem('app-theme', isDark ? 'dark' : 'light');
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
   const savedTheme = localStorage.getItem('app-theme');
   if (savedTheme === 'light') {
       // Only use light mode if explicitly chosen
       themeToggle.textContent = '🌙';
   } else {
       // Default to dark mode
       body.classList.add('dark-mode');
       themeToggle.textContent = '☀️';
       if (!savedTheme) {
           localStorage.setItem('app-theme', 'dark');
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
   - DragonFlux Klein: 7863 → 8001
   - Wan2GP: 7864 → 8002
   - Dashboard remains at 8100, Dragonsight at 8080
2. **✅ Removed legacy components**:
   - Deleted Qwen Vision (legacy) and `venv_qwen`
   - Deleted LTX-Video and LTX-2 projects
   - Deleted orphaned `/Wan2GP/` directory (63GB)
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
