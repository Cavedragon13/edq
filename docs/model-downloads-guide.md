# Model Download Guide - New Tools (2026-02-15)

## Quick Start: Background Downloads

Run this during idle time to pre-download all models:

```bash
cd /srv/containers/edq
bash scripts/download_new_models.sh
```

This is:

- ✅ **Safe to interrupt** (Ctrl+C) and resume later
- ✅ **Idempotent** (won't re-download existing files)
- ✅ **Resumable** (uses `--resume-download` flag)

Expected time: **2-4 hours** depending on network speed
Expected disk: **~70GB total**

---

## Individual Tool Setup

### 1. SoulX-Singer (~8GB) - EASIEST

**Status:** ✅ Ready to use after model download

```bash
source /srv/containers/edq/venv_soulxsinger/bin/activate
pip install -U huggingface_hub

hf download Soul-AILab/SoulX-Singer \
  --local-dir /srv/containers/edq/models/SoulX-Singer

hf download Soul-AILab/SoulX-Singer-Preprocess \
  --local-dir /srv/containers/edq/models/SoulX-Singer-Preprocess
```

**Launch:**

```bash
bash scripts/start_soulxsinger.sh
# Access at http://192.168.7.226:8023
```

**Update webui.py paths:**
Edit `/srv/containers/edq/projects/SoulX-Singer/webui.py` to point to downloaded models.

---

### 2. JustDubit (~50GB) - NEEDS CONFIGURATION

**Status:** ⚠️ Models + script configuration needed

```bash
cd /srv/containers/edq/projects/just-dub-it
/home/edq/.local/bin/uv pip install huggingface_hub

hf download justdubit/justdubit \
  --local-dir /srv/containers/edq/models/justdubit
```

**After download, locate these files in the model directory:**

- `ltx-2-19b-dev.safetensors` (main model)
- `ltx-2-19b-ic-lora-lipdubbing.safetensors` (lip-sync LoRA)
- `ltx-2-19b-distilled-lora-384.safetensors` (distilled LoRA)
- `ltx-2-spatial-upscaler-x2-1.0.safetensors` (upscaler)
- `gemma-3-12b-it-qat-q4_0-unquantized/` (text encoder folder)

**Update script paths:**
Edit `/srv/containers/edq/scripts/justdubit_gradio.py`:

```python
# Replace these placeholders:
"--checkpoint_path", "/srv/containers/edq/models/justdubit/ltx-2-19b-dev.safetensors",
"--gemma_root", "/srv/containers/edq/models/justdubit/gemma-3-12b-it-qat-q4_0-unquantized",
"--distilled_lora_path", "/srv/containers/edq/models/justdubit/ltx-2-19b-distilled-lora-384.safetensors",
"--spatial_upsampler_path", "/srv/containers/edq/models/justdubit/ltx-2-spatial-upscaler-x2-1.0.safetensors",
"--lora", "/srv/containers/edq/models/justdubit/ltx-2-19b-ic-lora-lipdubbing.safetensors",
```

**Launch:**

```bash
bash scripts/start_justdubit.sh
# Access at http://192.168.7.226:8022
```

---

### 3. DeepGen 1.0 diffusers (~14GB) - READY

**Status:** ✅ Ready. Uses the local diffusers package, not the old xtuner/mmengine route.

#### Setup Runtime

```bash
cd /srv/containers/edq
bash scripts/setup_deepgen_diffusers.sh
```

This creates `/srv/containers/edq/venv_deepgen` and installs the pinned runtime used by the dashboard launcher:

- PyTorch CUDA 12.8
- diffusers 0.38.0
- transformers 4.57.6
- safetensors 0.8.0rc0
- Gradio, accelerate, qwen-vl-utils, sentencepiece, einops

Do not upgrade transformers casually. DeepGen generation failed with newer transformers because the bundled Qwen2.5-VL call shape changed.

#### Download Models Before First Launch

```bash
cd /srv/containers/edq
bash scripts/download_deepgen_models.sh
```

The launcher expects a complete local snapshot at:

```text
/srv/containers/edq/models/deepgen-1.0-diffusers
```

The download script checks required files and refuses incomplete `.incomplete` shards. The dashboard launcher is intentionally local-only, so it will fail fast instead of starting a surprise first-run model download.

#### Launch

```bash
cd /srv/containers/edq
bash scripts/start_deepgen.sh
# Access at http://192.168.7.226:8024
```

Outputs are written to:

```text
/home/edq/ai_generated/deepgen
```

---

## Dependency Conflict Resolution

### DeepGen diffusers setup

The old xtuner/mmengine plan is retired. Use `scripts/setup_deepgen_diffusers.sh`, `scripts/download_deepgen_models.sh`, and `scripts/start_deepgen.sh`.

The model package already includes the VLM weights, connector, transformer, and VAE, so do not separately wire `Qwen/Qwen2.5-VL-3B-Instruct` unless the upstream package changes.

---

## Disk Space Summary

| Tool         | Models    | Venv      | Total     |
| ------------ | --------- | --------- | --------- |
| SoulX-Singer | ~8GB      | ~8GB      | ~16GB     |
| JustDubit    | ~50GB     | ~8GB      | ~58GB     |
| DeepGen      | ~14GB     | ~7GB      | ~21GB     |
| **TOTAL**    | **~68GB** | **~22GB** | **~90GB** |

---

## Testing Checklist

### SoulX-Singer

- [ ] Models downloaded to `/srv/containers/edq/models/SoulX-Singer`
- [ ] Preprocessing models downloaded
- [ ] webui.py updated with model paths
- [ ] Launch successful on port 8023
- [ ] Test singing synthesis with sample audio

### JustDubit

- [ ] All 5 model files located in downloaded repo
- [ ] Model paths updated in `justdubit_gradio.py`
- [ ] Launch successful on port 8022
- [ ] Test video dubbing with short sample

### DeepGen

- [x] Diffusers runtime installed in `/srv/containers/edq/venv_deepgen`
- [x] Models downloaded to `/srv/containers/edq/models/deepgen-1.0-diffusers`
- [x] Launch successful on port 8024
- [x] Text-to-image generation tested
- [x] Output saved under `/home/edq/ai_generated/deepgen`
- [x] 2026-05-08 QA: prompt-following Valyria smoke output verified at `/home/edq/ai_generated/deepgen/deepgen_20260508_122452.png`

---

## Troubleshooting

### "Models not found" Error

```bash
# Check model directory
ls -lh /srv/containers/edq/models/

# Re-run download script
bash scripts/download_new_models.sh
```

### DeepGen Import Errors

```bash
# Verify dependencies
source /srv/containers/edq/venv_deepgen/bin/activate
python -c "import xtuner; import mmengine; print('✓ OK')"

# If fails, run fix script
bash scripts/fix_deepgen_deps.sh
```

### CUDA Out of Memory

```bash
# Each tool already sets this, but verify:
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

# Only run ONE GPU-heavy tool at a time
# Stop other services via Dragonsuite dashboard
```

---

**Last Updated:** 2026-02-15
**Next Review:** After testing all three tools
