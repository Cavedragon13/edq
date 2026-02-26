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
- First launch downloads ~10GB of model weights
- Generation speed: ~1x real-time (2 min song = ~2 min generation)
- Use section tags in lyrics: `[Verse]`, `[Chorus]`, `[Bridge]`, `[Intro]`, `[Outro]`
- Style tags are comma-separated: `piano,happy,uplifting,pop`
- Supports multi-language lyrics

---

## ACE-Step 1.5 (Music Generation)

**Port:** 8021
**Purpose:** Ultra-fast commercial-grade music generation (quality between Suno v4.5 and v5)

### Launch

```bash
cd /srv/containers/edq
bash scripts/start_ace_step.sh
```

**Access at:** `http://192.168.7.226:8021`

### Configuration

- **Location**: `projects/ACE-Step-1.5/`
- **Launcher**: `scripts/start_ace_step.sh`
- **Venv**: Managed by `uv` (`.venv` inside project directory)
- **Requirements**: ~4GB VRAM, Python 3.11+
- **Output**: WAV/MP3 files saved to project directory

### Models

- DiT: `acestep-v15-turbo` (8-step inference)
- LM: `acestep-5Hz-lm-1.7B` (for 16GB VRAM)

### Features

- **Ultra-fast**: <10 seconds per song on RTX 3090 (vs HeartMuLa's ~2 minutes)
- **Low VRAM**: <4GB VRAM (can run alongside other services)
- **Duration**: 10 seconds to 10 minutes per song
- **Multi-language lyrics**: 50+ languages supported
- **Advanced editing**: Cover generation, selective repaint, vocal-to-BGM conversion
- **Reference audio**: Style guidance from audio samples
- **LoRA training**: One-click training from 8 songs (~1 hour on RTX 3090)
- **Batch generation**: Up to 8 songs simultaneously
- **Track separation**: Extract individual stems
- **Metadata control**: BPM, key/scale, time signature

### Notes

- Uses `uv` package manager instead of traditional venv
- Much faster and lower VRAM than HeartMuLa
- Can run alongside other services

### Tips

Much faster and lower VRAM than HeartMuLa; can run alongside other services
