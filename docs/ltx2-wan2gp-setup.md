# LTX-2 and WanGP2 Setup Guide

**Created:** 2026-02-08
**Purpose:** Solve model download issues and provide dedicated LTX-2 interface

## Problem Solved

**Issue:** WanGP2 UI showed stuck countdown ("10937.0/0.0s") when trying to download LTX-2 model.

**Root Cause:** UI downloads models on-demand, which can be confusing. The countdown was a UI bug while waiting for model selection.

**Discovery:** LTX-2 19B FP8 model (21GB) was actually already downloaded, along with control LoRAs!

## Solutions Implemented

### 1. Model Download Script ✅

**Location:** `/srv/containers/edq/scripts/wan2gp_download_models.py`

**Purpose:** Pre-download all WanGP2 models to avoid UI confusion.

**Usage:**
```bash
# Download recommended models (16GB VRAM optimized)
/srv/containers/edq/venv_wan2gp/bin/python scripts/wan2gp_download_models.py

# Download ALL available models
/srv/containers/edq/venv_wan2gp/bin/python scripts/wan2gp_download_models.py --all

# Download specific models
/srv/containers/edq/venv_wan2gp/bin/python scripts/wan2gp_download_models.py ltx2_19B ovi_1_1 flux2_klein_4b
```

**Recommended Models:**
- ✅ **LTX-2 19B** - Already downloaded (21GB FP8 + LoRAs)
- **Wan 2.2 Ovi** - 6GB + 6GB audio (fastest, speaking characters)
- **Flux 2 Klein 4B** - Image generation
- **Wan 2.2 Image-to-Video** - 14GB
- **Wan 2.2 Text-to-Video** - 14GB

### 2. Dedicated LTX-2 Interface ✅

**New Service:** LTX-2 Video (Port 8016)

**Files Created:**
- `/srv/containers/edq/scripts/ltx2_gradio.py` - Simplified Gradio interface
- `/srv/containers/edq/scripts/start_ltx2.sh` - Launcher
- Added to `config/dragonsuite.json` - Dashboard integration

**Features:**
- Clean, focused UI for LTX-2 only
- No model switching confusion
- Text-to-video with audio soundtrack
- Optional start/end keyframes
- Supports dialogue tags `<S>...<E>` and audio prompts
- 20 second maximum video length
- Dark mode by default

**Launch:**
```bash
# Via dashboard (port 8100)
# Navigate to Video category → "LTX-2 Video" → Start

# Or directly
bash scripts/start_ltx2.sh
```

**Access:**
- Local: `http://localhost:8016`
- LAN: `http://192.168.7.226:8016`

**Output:** `~/ai_generated/ltx2/`

## Model Inventory (Current)

**Already Downloaded:**
```
/srv/containers/edq/projects/Wan2GP/ckpts/
├── ltx-2-19b-dev-fp8_diffusion_model.safetensors (21GB)
├── ltx-2-19b-ic-lora-canny-control.safetensors (625MB)
├── ltx-2-19b-ic-lora-depth-control.safetensors (625MB)
├── ltx-2-19b-ic-lora-pose-control.safetensors (625MB)
├── wan2.1_image2video_480p_14B_quanto_mbf16_int8.safetensors (16GB)
├── wan2.1_text2video_14B_quanto_mbf16_int8.safetensors (14GB)
├── Wan2.1_VAE.safetensors (485MB)
└── Wan2.1_VAE_upscale2x_imageonly_real_v1.safetensors (485MB)
```

**Total Downloaded:** ~53GB

**Storage Available:** 4TB (plenty of room for all models!)

## Available Models (158 configurations!)

The WanGP2 project includes configurations for 158 different models across multiple categories:

**Video Generation:**
- LTX-2 (19B, distilled versions, GGUF quantized)
- Wan 2.1/2.2 (text2video, image2video, variations)
- HunyuanVideo (1.5, distilled, various resolutions)
- Kandinsky 5 (lite, pro, different durations)
- LongCat (video, avatar modes)
- VACE (14B, cocktail, lightning variants)

**Image Generation:**
- Flux 2 (Dev, Klein 4B/9B, Chroma, Kontext, Schnell, SRPO)
- Z-Image (Base, Control, TwinFlow Turbo)
- Qwen-Image (20B, Edit, Layered, variants)

**Audio/TTS:**
- Qwen3-TTS (Base, CustomVoice, VoiceDesign)
- HeartMuLa (music generation)
- Chatterbox, MMAudio

**Specialized:**
- Animation, avatar, portrait modes
- Video editing, upsampling
- Control networks (pose, depth, canny)

## Usage Tips

### LTX-2 Video Generation

**Prompt Structure:**
```
[Scene description]. [Character 1 action], says "<S>dialogue<E>". [Character 2 action], says "<S>dialogue<E>". [Camera movement]. Audio: [background sounds, music, effects].
```

**Example:**
```
A warm sunny backyard. The camera starts in a tight cinematic close-up of a woman
and a man in their 30s, facing each other with serious expressions. The woman,
emotional and dramatic, says softly, "<S>That's it... Dad's lost it. And we've
lost Dad.<E>" The man exhales, slightly annoyed: "<S>Stop being so dramatic, Jess.<E>"
A beat. He glances aside, then mutters defensively, "<S>He's just having fun.<E>"
The camera slowly pans right, revealing the grandfather in the garden wearing
enormous butterfly wings, waving his arms in the air like he's trying to take off.
He shouts, "<S>Wheeeew!<E>" as he flaps his wings with full commitment. The woman
covers her face, on the verge of tears. The tone is deadpan, absurd, and quietly tragic.
Audio: Birds chirping, gentle wind, rustling leaves, faint laughter.
```

**Settings:**
- **Video Length:** 33-241 frames (33≈1s, 121≈5s, 241≈10s at 24fps)
- **Inference Steps:** 40 recommended (20-60 range)
- **Guidance Scale:** 4.0 (how closely to follow prompt)
- **Seed:** -1 for random, or specific number for reproducibility

**VRAM Usage:**
- Fits in 16GB with CPU offloading
- Close other GPU services first
- Uses `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`

### WanGP2 Full Interface

**Use WanGP2 (port 8002) when you want:**
- Model switching between different architectures
- Advanced features (LoRAs, control nets, sliding window)
- Access to all 158+ model configurations
- Experimental features and new model testing

**Use LTX-2 (port 8016) when you want:**
- Simple, focused video generation
- No confusion about model selection
- Dedicated interface for LTX-2 only
- Quick access without UI clutter

## Troubleshooting

### UI Countdown Stuck

**Symptom:** Counter shows "10937.0/0.0s" and keeps counting

**Cause:** No model selected yet, UI waiting for selection

**Fix:**
1. Select a model from dropdown
2. Or use dedicated LTX-2 interface (port 8016)

### Model Not Found

**Check if downloaded:**
```bash
ls -lh /srv/containers/edq/projects/Wan2GP/ckpts/
```

**Download manually:**
```bash
cd /srv/containers/edq/projects/Wan2GP/ckpts
wget https://huggingface.co/DeepBeepMeep/MODEL_NAME/resolve/main/file.safetensors
```

**Or use downloader script** (recommended)

### CUDA Out of Memory

**Solutions:**
- Close other GPU services (check port 8001-8019)
- Reduce video length (fewer frames)
- Lower resolution if option available
- Ensure `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` is set

### Generation Takes Too Long

**Expected times (16GB RTX 5070 Ti):**
- **5 second video:** ~2-5 minutes (40 steps)
- **10 second video:** ~5-10 minutes (40 steps)
- **20 second video:** ~10-20 minutes (40 steps)

**Overnight generation is normal** for high-quality 10-20s videos with many inference steps.

## Next Steps

1. **Download Additional Models:**
   ```bash
   # Get Wan 2.2 Ovi (fastest, 6GB)
   /srv/containers/edq/venv_wan2gp/bin/python scripts/wan2gp_download_models.py ovi_1_1

   # Get Flux 2 Klein 4B (image gen)
   /srv/containers/edq/venv_wan2gp/bin/python scripts/wan2gp_download_models.py flux2_klein_4b

   # Or get everything
   /srv/containers/edq/venv_wan2gp/bin/python scripts/wan2gp_download_models.py --all
   ```

2. **Test LTX-2 Interface:**
   - Launch via dashboard or `bash scripts/start_ltx2.sh`
   - Try default prompt
   - Experiment with keyframes

3. **Explore Model Variety:**
   - Check `/srv/containers/edq/projects/Wan2GP/defaults/` for all configs
   - Read model descriptions in JSON files
   - Test different models via WanGP2 interface (port 8002)

4. **Optimize Workflow:**
   - Pre-download frequently used models
   - Use LTX-2 interface for simple video gen
   - Use WanGP2 for experimentation and advanced features

## Resources

- **WanGP2 Project:** `/srv/containers/edq/projects/Wan2GP/`
- **Model Configs:** `projects/Wan2GP/defaults/` (158 JSON files)
- **Checkpoints:** `projects/Wan2GP/ckpts/` (downloaded models)
- **LTX-2 Output:** `~/ai_generated/ltx2/`
- **WanGP2 Output:** `~/ai_generated/wan2gp/`

---

**Status:** Setup complete, models downloading in background
**Storage Used:** ~53GB (models) + outputs
**Storage Available:** ~4TB (plenty of room)
**Interfaces:** WanGP2 (8002) + dedicated LTX-2 (8016)
