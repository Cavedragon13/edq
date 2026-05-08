# Image Generation Services

## DragonFlux Klein

**Port:** 8001
**Purpose:** FLUX.2-klein image generation with LoRA support

### Launch

```bash
cd /srv/containers/edq
bash scripts/start_flux2_klein.sh
```

**Access at:** `http://192.168.7.226:8001`

### Configuration

- **Script**: `scripts/flux2_klein_gradio.py`
- **Launcher**: `scripts/start_flux2_klein.sh`
- **Venv**: `venv_flux2`
- **Output**: `~/ai_generated/flux2-klein/`
- **Model loading**: local Hugging Face cache only for FLUX.2-klein 4B/9B; launcher fails fast if cached snapshots are missing

### Features

- LoRA model loading from `~/models/loras/flux-klein/`
- Output saves to `~/ai_generated/flux2-klein/`
- Gradio interface

### Key Considerations

- GPU-heavy (loads FLUX model into VRAM)
- LoRA support via `~/models/loras/flux-klein/`
- Output saves to `~/ai_generated/flux2-klein/`
- 4B mode is the fast health-check target; 9B and FLUX.1-dev are heavier.

### Verified Outputs

- 2026-05-07: 4-step 512x512 smoke produced a clean, prompt-following brass `DRAGON` sign under `~/ai_generated/flux2-klein/`.

---

## Z-Anime

**Port:** 8008
**Purpose:** Anime fine-tune of Z-Image Base using the SeeSee21/Z-Anime diffusers package

### Launch

```bash
cd /srv/containers/edq
bash scripts/start_zanime.sh
```

**Access at:** `http://192.168.7.226:8008`

### Configuration

- **Script**: `scripts/zanime_gradio.py`
- **Launcher**: `scripts/start_zanime.sh`
- **Venv**: `venv_zimage`
- **Models**: `/srv/containers/edq/models/zanime/diffusers`
- **Output**: `~/ai_generated/zanime/`
- **Model loading**: local diffusers directory only; AIO safetensors are ComfyUI checkpoints and should not be loaded by this app

### Smoke Notes

- Short 12-step runs may produce poor prompt following.
- 40-step `Diffusers Base BF16` runs produced a prompt-following anime portrait with horns, red hair, bronze cheek scales, and amber eyes.

---

## Z-Image Base + Turbo

**Port:** 8011
**Purpose:** Alibaba Tongyi's 6B parameter text-to-image with dual model support

### Launch

```bash
cd /srv/containers/edq
bash scripts/start_zimage.sh
```

**Access at:** `http://192.168.7.226:8011`

### Configuration

- **Script**: `scripts/zimage_base_gradio.py`
- **Launcher**: `scripts/start_zimage.sh`
- **Venv**: `venv_zimage`
- **Requirements**: ~13-14GB VRAM (bf16) with CPU offloading
- **Output**: `~/ai_generated/zimage/`
- **Model loading**: local Hugging Face cache only (`local_files_only=True`); launcher fails fast if cached snapshots are missing

### Models

- **Base**: Tongyi-MAI/Z-Image (Apache 2.0 license) ✅ Available
  - 30-step inference with CFG scaling (7-10 recommended)
  - Negative prompt support
  - Superior photorealism, hands, text rendering
- **Turbo**: Tongyi-MAI/Z-Image-Turbo ✅ Available
  - 8-step fast inference (4x faster than Base)
  - CFG fixed at 1.0 for optimal results
  - ~5-10 seconds per image
- **Fast Mode (Distilled LoRA)**: Z-Image-Fun-Lora-Distill ✅ Available
  - 4-step or 8-step ultra-fast inference (4-8x faster than Base)
  - CFG distilled to 1.0 (auto-applied)
  - Compatible with both Base and Turbo models
  - LoRA scale 0.7-0.8 recommended
  - Maintains compatibility with other Z-Image LoRAs
- **ControlNet Union 2.1**: Available through the VideoX-Fun bridge when local cached weights are present
  - Multi-condition control: Canny, Depth, Pose, HED, MLSD
  - Uses cached `alibaba-pai/Z-Image-Turbo-Fun-Controlnet-Union-2.1`

### Features

- Model selector (Base vs Turbo)
- Fast Mode checkbox for distilled LoRA (4-step or 8-step)
- LoRA support from `/srv/containers/edq/models/loras/zimage/`
- Multiple aspect ratio presets
- Control image preprocessing (ready for ControlNet when available)

### Key Considerations

- Dual model support: Base (30-step CFG) or Turbo (8-step fast)
- No first-run downloads: refresh or prefetch the Hugging Face cache outside launch if upstream model snapshots are missing

### Verified Outputs

- 2026-05-07: 256x256 Base smoke generated a brass desk sign under `~/ai_generated/zimage/`.
- 2026-05-07: Real-ESRGAN and Creative Upscaler successfully consumed that output downstream.
- **Base model features:**
  - CFG scaling 7-10 recommended
  - Negative prompt support
  - 30 steps for quality output
  - Superior photorealism and text rendering
  - ~20-30 seconds per image
- **Turbo model features:**
  - 8-step fast inference (4x faster)
  - CFG fixed at 1.0 for optimal 8-step results
  - Perfect for rapid iteration and prototyping
  - ~5-10 seconds per image
- **ControlNet Union 2.1 (Coming Soon):**
  - Infrastructure ready but waiting for diffusers v0.37+ support
  - `ZImageControlNetPipeline` not yet available in diffusers 0.36.0
  - Workaround: Use [VideoX-Fun repository](https://github.com/aigc-apps/VideoX-Fun) for immediate ControlNet access
- **LoRA support:**
  - Place LoRA files in `~/models/loras/zimage/`
  - Works with both Base and Turbo models
  - Adjust LoRA scale 0.0-2.0 (1.0 default)
- First launch downloads Base model (~12GB) on-demand
- Turbo model (~12GB) downloads when first used
- Uses CPU offloading to fit in 16GB VRAM
- Close other GPU services if you encounter OOM errors
- opencv-python installed for future ControlNet preprocessing

### Tips

- **Base mode**: CFG 7-10, 30 steps, use negative prompts
- **Turbo mode**: 8 steps (CFG fixed at 1.0), ~5-10 seconds per image
- **Fast Mode**: Enable checkbox, use 4 or 8 steps, LoRA scale 0.7-0.8, CFG auto-set to 1.0
- **ControlNet**: Infrastructure ready, waiting for diffusers library support

---

## Qwen-Image-Layered

**Port:** 8013
**Purpose:** Decompose images into multiple RGBA layers for advanced editing

### Launch

```bash
cd /srv/containers/edq
bash scripts/start_qwen_image_layered.sh
```

**Access at:** `http://192.168.7.226:8013`

### Configuration

- **Script**: `scripts/qwen_image_layered_gradio.py`
- **Launcher**: `scripts/start_qwen_image_layered.sh`
- **Venv**: `venv_qwen_image_layered`
- **Model**: Qwen/Qwen-Image-Layered (Apache 2.0 license)
- **Requirements**: ~14-16GB VRAM (uses CPU offloading)
- **Output**: `~/ai_generated/qwen-layered/`

### Features

- Variable layer count (2-8 layers)
- RGBA PNG export for each layer
- ZIP download of all layers
- PPTX export for presentations
- Recursive decomposition possible

### Key Considerations

- First launch downloads ~12GB of model weights
- Uses ~14-16GB VRAM with CPU offloading enabled
- Close other GPU services before use
- 640px resolution recommended (1024px uses more VRAM)
- Downloads include ZIP and optional PPTX of all layers

---

## Real-ESRGAN (Image Upscaling)

**Port:** 8010
**Purpose:** AI image upscaling with multiple models

### Launch

```bash
cd /srv/containers/edq
bash scripts/start_realesrgan.sh
```

**Access at:** `http://192.168.7.226:8010`

### Configuration

- **Script**: `scripts/realesrgan_server.py`
- **Launcher**: `scripts/start_realesrgan_native.sh`
- **Venv**: `venv_realesrgan`
- **Requirements**: ~4GB VRAM
- **Output**: `~/ai_generated/realesrgan/`

### Models

- RealESRGAN_x4plus - General photos (default)
- RealESRGAN_x4plus_anime_6B - Anime/illustration
- RealESRGAN_x2plus - 2x upscaling (faster)
- realesr-general-x4v3 - Compact with denoise

### Features

- Up to 8x output scaling
- Face enhancement (GFPGAN)
- Tiling for large images
- Clipboard paste support

### Key Considerations

- Launcher fails fast if local model files are missing; run `scripts/download_realesrgan_models.sh` outside launch if needed
- ~4GB VRAM for most models
- Use tiling (256/512) for large images to save VRAM
- Face enhancement uses the local GFPGAN checkpoint
- Anime model works best for illustrations/anime art

### Verified Outputs

- 2026-05-07: 2x API upscale converted a 256x256 Z-Image PNG into a 512x512 PNG under `~/ai_generated/realesrgan/`.

---

## Creative Upscaler

**Port:** 8018
**Purpose:** Prompt-guided creative upscaling with FLUX + ControlNet Tile

### Launch

```bash
cd /srv/containers/edq
bash scripts/start_creative_upscale.sh
```

**Access at:** `http://192.168.7.226:8018`

### Configuration

- **Script**: `scripts/creative_upscale_gradio.py`
- **Launcher**: `scripts/start_creative_upscale.sh`
- **Venv**: `venv_flux2`
- **Models**: `/srv/containers/edq/models/creative_upscale`
- **Output**: `~/ai_generated/creative-upscale/`
- **Model loading**: local files only; launcher fails fast on missing or incomplete shards

### Key Considerations

- This is a slow smoke target, not a quick health check.
- 2026-05-07: 2x, 20-step, 256->512 chained smoke took about 7.5 minutes.
- Use Real-ESRGAN for quick upscaling checks; use Creative Upscaler when prompt-guided detail matters.

### Verified Outputs

- 2026-05-07: Prompt-guided 2x upscale consumed the Z-Image brass sign and saved a 512x512 PNG under `~/ai_generated/creative-upscale/`.

---

## Rembg (Background Removal)

**Port:** 8012
**Purpose:** Remove backgrounds from images

### Configuration

- **Venv**: `venv_rembg`
