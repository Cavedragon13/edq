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

### Features

- LoRA model loading from `~/models/loras/flux-klein/`
- Output saves to `~/ai_generated/flux2-klein/`
- Gradio interface

### Key Considerations

- GPU-heavy (loads FLUX model into VRAM)
- LoRA support via `~/models/loras/flux-klein/`
- Output saves to `~/ai_generated/flux2-klein/`

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
- **ControlNet Union 2.1**: 🚧 Coming Soon (Pending diffusers v0.37+)
  - Planned: Multi-condition control (Canny, Depth, Pose, HED, MLSD)
  - Planned: Professional-grade spatial control (15+ layer blocks)
  - Workaround: Use [VideoX-Fun](https://github.com/aigc-apps/VideoX-Fun) repository

### Features

- Model selector (Base vs Turbo)
- Fast Mode checkbox for distilled LoRA (4-step or 8-step)
- LoRA support from `~/models/loras/zimage/`
- Multiple aspect ratio presets
- Control image preprocessing (ready for ControlNet when available)

### Key Considerations

- Dual model support: Base (30-step CFG) or Turbo (8-step fast)
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

- **Script**: `scripts/realesrgan_gradio.py`
- **Launcher**: `scripts/start_realesrgan.sh`
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

- First launch downloads ~200MB of model weights
- ~4GB VRAM for most models
- Use tiling (256/512) for large images to save VRAM
- Face enhancement adds GFPGAN (~500MB additional download)
- Anime model works best for illustrations/anime art

---

## Rembg (Background Removal)

**Port:** 8012
**Purpose:** Remove backgrounds from images

### Configuration

- **Venv**: `venv_rembg`
