# Video & Music Generation Services

## Wan2GP (Video Generation)

**Port:** 8002
**Purpose:** Wan 2.0 video generation

### Launch

```bash
cd /srv/containers/edq
bash scripts/start_wan2gp.sh
```

**Access at:** `http://192.168.7.226:8002`

### Configuration

- **Location**: `projects/Wan2GP/`
- **Launcher**: `scripts/start_wan2gp.sh`
- **Venv**: `venv_wan2gp`

### Recommended Models (16GB VRAM)

- Wan 2.2 Ovi (6GB) - fastest
- LTX 2 (8GB)
- Flux 2 int8 (8GB)

### Key Considerations

- GPU-heavy, only run one GPU service at a time
- Multiple model options for different VRAM budgets
- Video generation can take several minutes

---

## HeartMuLa (Music Generation)

**Port:** 8004
**Purpose:** AI music generation from lyrics and style tags (Suno-level quality, open source)

### Launch

```bash
cd /srv/containers/edq
bash scripts/start_heartmula.sh
```

**Access at:** `http://192.168.7.226:8004`

### Configuration

- **Location**: `projects/heartmula/`
- **Launcher**: `scripts/start_heartmula.sh`
- **Venv**: `venv_heartmula`
- **Model**: HeartMuLa-oss-3B (Apache 2.0 license)
- **Requirements**: ~12GB VRAM, ~10GB disk for models
- **Output**: `~/ai_generated/heartmula/`

### Features

- Lyrics-to-music generation
- Section structure support ([Verse], [Chorus], [Bridge], etc.)
- Style tags (instruments, mood, genre, tempo)
- Adjustable temperature, top-k, CFG scale
- Output: MP3 files saved to `~/ai_generated/heartmula/`

### Key Considerations

- GPU-heavy (~12GB VRAM), only run one GPU service at a time
- Model weights are cached under `projects/heartmula/ckpt/`; do not rely on first-run downloads during a creative session
- Generation speed: ~1x real-time (2 min song = ~2 min generation)
- Use section tags in lyrics: `[Verse]`, `[Chorus]`, `[Bridge]`, `[Intro]`, `[Outro]`
- Style tags are comma-separated: `piano,happy,uplifting,pop`
- Supports multi-language lyrics

### QA Notes

- 2026-05-08: Dashboard launch and short music-generation smoke passed using the `stale_ip_blues` lyrics/style asset.
- Verified persistent output: `/home/edq/ai_generated/heartmula/heartmula_20260508_084502.mp3` (30.12s, 48kHz stereo MP3, non-zero).
- Launcher stale-process detection now checks the HeartMuLa app path and listening port.
- Gradio 6 cleanup: `theme` is passed to `launch()`.

---

## ACE-Step 1.5 XL (Music Generation)

**Port:** 8021
**Purpose:** Local music generation with ACE-Step 1.5 XL / Turbo models

### Launch

```bash
cd /srv/containers/edq
bash scripts/start_ace_step.sh
```

**Access at:** `http://192.168.7.226:8021`

### Configuration

- **Location**: `projects/ACE-Step-1.5-xl/`
- **Launcher**: `scripts/start_ace_step.sh`
- **Venv**: Managed by `uv` (`.venv` inside project directory)
- **Requirements**: Python 3.11+, GPU-heavy; test with no other on-demand GPU service running
- **Output**: MP3/JSON batches saved under `/home/edq/ai_generated/ace-step-xl/` (symlink to `projects/ACE-Step-1.5-xl/gradio_outputs/`)

### Models

- DiT: `acestep-v15-xl-turbo` (8-step inference)
- LM: `acestep-5Hz-lm-1.7B` (for 16GB VRAM)

### Features

- **Fast generation after warm start**: 10s smoke test generated in a few seconds after models were loaded
- **GPU-heavy warm runtime**: observed around 13GB VRAM while loaded; keep it isolated from other on-demand GPU services
- **Duration**: 10 seconds to 10 minutes per song
- **Multi-language lyrics**: 50+ languages supported
- **Advanced editing**: Cover generation, selective repaint, vocal-to-BGM conversion
- **Reference audio**: Style guidance from audio samples

### QA Notes

- 2026-05-08: Started from Dashboard, confirmed model initialization and Gradio on port 8021.
- Verified generation via live Gradio API endpoint `/generation_wrapper`; public client input list has 59 parameters and omits hidden state components.
- Verified prompt-following metadata and persistent output for stale-IP-blues smoke test:
  `/home/edq/ai_generated/ace-step-xl/batch_1778256953/7e4efff8-5b05-3f8c-d2e9-219ca3b28385.mp3`
  plus matching JSON, 10.032s, 48kHz stereo MP3.
- 2026-05-08: Stop behavior hardened with `scripts/stop_ace_step.sh`; verified one dashboard stop after full model load drops port 8021 and releases VRAM from ~13.4GB to ~1.2GB.

### Notes

- Uses `uv` package manager instead of traditional venv.
- Treat as a GPU-heavy service on udragon; stop it before starting another on-demand GPU generator.
- **LoRA training**: One-click training from 8 songs (~1 hour on RTX 3090)
- **Batch generation**: Up to 8 songs simultaneously
- **Track separation**: Extract individual stems
- **Metadata control**: BPM, key/scale, time signature

---

## Foundation-1 (Music Loop Generation)

**Port:** 8027
**Purpose:** Short music loop generation with WAV and MIDI output

### Configuration

- **Location**: `projects/foundation-1/`
- **Launcher**: `scripts/start_foundation1.sh`
- **Output**: `/home/edq/ai_generated/foundation-1/`

### QA Notes

- 2026-05-08: Dashboard launch and short loop-generation smoke passed.
- Verified persistent outputs:
  - `/home/edq/ai_generated/foundation-1/Rhodes_electric_piano_chords_upright_bass_brushed_snare_warm_sysadmin_blues_loop_G_major_soulful_and_rhythmic_clean_studio_recording_G_major_4_bars_120BPM_4242.wav` (8.0s, 44.1kHz stereo WAV, non-zero)
  - `/home/edq/ai_generated/foundation-1/Rhodes_electric_piano_chords_upright_bass_brushed_snare_warm_sysadmin_blues_loop_G_major_soulful_and_rhythmic_clean_studio_recording_G_major_4_bars_120BPM_4242_basic_pitch.mid` (standard MIDI file, non-zero)
- App config now points `generations_directory` at `/home/edq/ai_generated/foundation-1`.
- Dashboard metadata now includes `output_dir` for Foundation-1.
- Launcher stale-process detection now checks the Foundation-1 app path and listening port.
