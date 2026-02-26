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

### 3. DeepGen 1.0 (~10GB) - DEPENDENCY WORKAROUND

**Status:** ⚠️ Dependencies resolved, models needed, inference incomplete

#### Step 1: Verify Dependencies

```bash
source /srv/containers/edq/venv_deepgen/bin/activate
pip list | grep -E "xtuner|mmengine|transformers"
```

Should show:

- ✅ xtuner==0.2.0
- ✅ mmengine==0.10.6
- ✅ bitsandbytes==0.45.0
- ⚠️ transformers==5.1.0 (xtuner wants 4.48.0)

#### Step 2: Test with Current Versions (Recommended First)

```bash
bash scripts/start_deepgen.sh
# Access at http://192.168.7.226:8024
```

The UI will show if model loading works with newer transformers.

#### Step 3: If It Fails, Downgrade Transformers

```bash
bash scripts/fix_deepgen_deps.sh
# Choose option 2 to downgrade transformers to 4.48.0
```

#### Step 4: Download Models

```bash
source /srv/containers/edq/venv_deepgen/bin/activate
huggingface-cli download deepgenteam/DeepGen-1.0 \
  --local-dir /srv/containers/edq/models/deepgen-1.0
```

#### Step 5: Complete Inference Pipeline

The Gradio UI (v2) can load the model but needs the inference call completed.
Reference: `/srv/containers/edq/projects/deepgen/scripts/text2image.py`

---

## Dependency Conflict Resolution

### DeepGen xtuner/mmengine Workaround

**The Problem:**

- DeepGen's `requirements.txt` has many version conflicts
- xtuner requires specific versions of transformers, mmengine, etc.
- Full `pip install -r requirements.txt` fails

**The Solution:**

1. Install core dependencies first (PyTorch, transformers, diffusers)
2. Install xtuner without dependencies (`--no-deps`)
3. Install mmengine with exact version xtuner needs
4. Install missing xtuner deps individually
5. Test with newer transformers (5.1.0) - may work despite warning
6. If fails, downgrade transformers to 4.48.0

**Current Status:**
✅ All dependencies installed
⚠️ transformers version mismatch (5.1.0 vs 4.48.0 wanted)
✅ Model can load (tested in v2 UI)
⚠️ Inference pipeline needs completion

---

## Disk Space Summary

| Tool         | Models    | Venv      | Total     |
| ------------ | --------- | --------- | --------- |
| SoulX-Singer | ~8GB      | ~8GB      | ~16GB     |
| JustDubit    | ~50GB     | ~8GB      | ~58GB     |
| DeepGen      | ~10GB     | ~6GB      | ~16GB     |
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

- [ ] Dependencies verified (xtuner, mmengine)
- [ ] Models downloaded to `/srv/containers/edq/models/deepgen-1.0`
- [ ] Launch successful on port 8024
- [ ] Model loading works (check UI status)
- [ ] If needed, transformers downgraded to 4.48.0
- [ ] Inference pipeline completed
- [ ] Test text-to-image generation

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
