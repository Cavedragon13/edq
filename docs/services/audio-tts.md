# Audio & Text-to-Speech Services

## Fish Speech

**Port:** 8003
**Purpose:** Expressive TTS with voice cloning (OpenAudio S1-mini, 0.5B params)

### Launch

```bash
cd /srv/containers/edq
bash scripts/start_fish_speech.sh
```

**Access at:** `http://192.168.7.226:8003`

### Configuration

- **Location**: `projects/fish-speech/`
- **Launcher**: `scripts/start_fish_speech.sh`
- **Venv**: `venv_fish_speech`
- **Requirements**: 12GB VRAM

### Features

- Zero-shot TTS (no reference audio needed)
- Voice cloning from 10-30s audio samples
- Emotion control markers (angry, sad, excited, etc.)
- Multi-language support (EN, CN, JP, DE, FR, ES, KO, AR, RU, etc.)
- Gradio web interface

### Key Considerations

- GPU-heavy (12GB VRAM), only run one GPU service at a time
- First launch downloads ~2GB model weights
- Voice cloning: place 10-30s audio samples in `projects/fish-speech/references/<voice_id>/sample.wav`
- Emotion markers: use `(angry)`, `(excited)`, `(sad)`, etc. in text
- Tone markers: `(whispering)`, `(shouting)`, `(in a hurry tone)`

---

## Qwen3-TTS

**Port:** 8009
**Purpose:** High-quality TTS with voice cloning and voice design

### Launch

```bash
cd /srv/containers/edq
bash scripts/start_qwen3_tts.sh
```

**Access at:** `http://192.168.7.226:8009`

### Configuration

- **Location**: `projects/qwen3-tts/`
- **Launcher**: `scripts/start_qwen3_tts.sh`
- **Venv**: `venv_qwen3_tts`
- **Models**: Qwen3-TTS-12Hz-1.7B (Base, CustomVoice, VoiceDesign)
- **Requirements**: ~6-8GB VRAM per model (with FlashAttention)
- **Output**: `~/ai_generated/qwen3-tts/`

### Features

- TTS with 9 predefined speakers + style control
- Voice cloning from reference audio
- Voice design from natural language descriptions
- Multi-language support (EN, CN, JP, KO, FR, DE, ES, PT, RU)
- Lazy model loading (one model at a time)

### Key Considerations

- GPU-heavy (~6-8GB VRAM per model), only run one GPU service at a time
- First launch downloads ~6GB of model weights (per model type)
- Three modes: TTS (speakers), Voice Clone, Voice Design
- Only one model loaded at a time for 16GB VRAM compatibility
- Switching tabs may reload models
- 9 predefined speakers: Aiden, Dylan, Eric, Ono_anna, Ryan, Serena, Sohee, Uncle_fu, Vivian
- Voice design: describe age, gender, tone, emotion, accent

### Tips

Switching tabs may reload models as only one is loaded at a time

---

## Qwen3-Audiobook

**Port:** 8014
**Purpose:** Convert documents to MP3 audiobooks using Qwen3-TTS

### Launch

```bash
cd /srv/containers/edq
bash scripts/start_qwen3_audiobook.sh
```

**Access at:** `http://192.168.7.226:8014`

### Configuration

- **Script**: `scripts/qwen3_audiobook_gradio.py`
- **Launcher**: `scripts/start_qwen3_audiobook.sh`
- **Venv**: Shares `venv_qwen3_tts`
- **Requirements**: CPU only (TTS uses GPU via port 8009)
- **Output**: `~/ai_generated/qwen3-audiobook/`

### Dependencies

**Requires**: Qwen3-TTS running on port 8009

### Supported Formats

- PDF (text-based)
- EPUB (e-books)
- DOCX/DOC (Word documents)
- TXT (plain text)

### Features

- 9 predefined speaker voices
- Custom style instructions
- Intelligent text chunking (~1200 words)
- Progress tracking

### Key Considerations

- Requires Qwen3-TTS running on port 8009 first
- Start TTS service: `bash scripts/start_qwen3_tts.sh`
- Shares venv with Qwen3-TTS (no separate installation)
- Supports PDF, EPUB, DOCX, DOC, TXT formats
- Text is chunked into ~1200 word segments for reliable TTS
- Long documents may take significant time to convert

### Tips

Start Qwen3-TTS first before using audiobook converter

---

## Dragonsong (Real-Time Music Generation)

**Port:** 8029
**Purpose:** Interactive real-time music generation via Google Lyria RealTime API — live prompt steering, parameter control, layer muting, record to WAV

### Launch

```bash
cd /srv/containers/edq
bash scripts/start_dragonsong.sh
```

**Access at:** `http://192.168.7.226:8029`

### Configuration

- **Server**: `scripts/dragonsong_server.py` (FastAPI WebSocket proxy)
- **UI**: `media/dragonsong.html` (native HTML/JS, no Gradio)
- **Launcher**: `scripts/start_dragonsong.sh`
- **Venv**: `venv_dragonsong` (google-genai, fastapi, uvicorn, python-dotenv)
- **Auth**: `GOOGLE_API_KEY` from `/srv/containers/edq/.env`
- **Requirements**: No GPU — cloud API

### Features

- 12 genre preset buttons (Lo-fi, Jazz, Ambient, Techno, Cinematic, Acoustic, etc.)
- Dual prompt blending with weight sliders
- Live parameter controls: BPM (60–200), density, brightness, guidance, temperature
- Scale selector (12 keys or Any) + Mode (Quality / Diversity / Vocalization)
- Layer toggles: mute bass, mute drums, bass+drums only
- Gapless Web Audio playback (48kHz stereo Int16 PCM streaming)
- Live waveform visualizer (canvas + AnalyserNode)
- Record button → client-side WAV download (no server round-trip)

### Key Considerations

- Uses Google Lyria RealTime API (`models/lyria-realtime-exp`, API v1alpha)
- WebSocket proxy: browser ↔ local FastAPI ↔ Google Lyria
- No GPU required — cloud API, uses `GOOGLE_API_KEY`
- Produces instrumental music only (no lyrics/vocals in standard mode)
- VOCALIZATION mode can produce wordless vocal elements
- Output: browser-side WAV recording; also saves timestamped WAVs to `~/ai_generated/dragonsong/` (if configured)

### Tips

- Click Play first to establish the WebSocket session, then adjust prompts/sliders live
- Use dual prompt blend to morph between two styles in real-time
- Record button captures the stream; save downloads a client-assembled WAV file

---

## Voxtral TTS

**Port:** 8042
**Purpose:** High-quality TTS via Mistral's Voxtral-4B-TTS-2603 (4B params, 24kHz, BF16)

### Launch

```bash
cd /srv/containers/edq
bash scripts/start_voxtral.sh
```

**Access at:** `http://192.168.7.226:8042`

### Configuration

- **Launcher**: `scripts/start_voxtral.sh`
- **Backend**: vLLM-Omni on port 9042 (localhost only)
- **Venv**: `venv_voxtral` (torch 2.10.0+cu128, vllm 0.18.0, vllm-omni 0.18.0)
- **Model**: `mistralai/Voxtral-4B-TTS-2603` (~16GB download, HF cache)
- **VRAM**: ~14GB (Stage 0 at 0.74, Stage 1 at 0.1 — set in voxtral_tts.yaml)
- **License**: CC BY NC 4.0 (non-commercial)

### Features

- 20 preset voices: casual/cheerful/neutral (EN), fr/es/de/it/pt/nl/hi male+female, ar_male
- Speed control (0.25x–4.0x)
- Output formats: wav, mp3, flac, opus, aac, pcm
- ~4–5s latency for a sentence, 24kHz mono output

### Setup Notes

- Run `scripts/download_voxtral_models.sh` before first use (downloads ~16GB + 20 voice .pt files)
- `config.json` stub must include `audio_config.speaker_id` dict (written by download script logic)
- YAML Stage 0 `gpu_memory_utilization` set to 0.74 (default 0.8 causes CUDA graph OOM on 16GB)
- Do NOT pass `--gpu-memory-utilization` to `vllm serve` — it overrides the per-stage YAML values
