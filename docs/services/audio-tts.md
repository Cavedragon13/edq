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
- OpenAudio S1-mini model weights are cached at `projects/fish-speech/checkpoints/openaudio-s1-mini/`
- `checkpoints/s2-pro/` is also cached, but treat Fish Speech S2-Pro as a hardware no-go on this 32GB RAM / 16GB RTX 5070 Ti host: a dashboard/direct startup test OOM-killed the Python loader during Llama checkpoint load.
- Voice cloning: place 10-30s audio samples in `projects/fish-speech/references/<voice_id>/sample.wav`
- Emotion markers: use `(angry)`, `(excited)`, `(sad)`, etc. in text
- Tone markers: `(whispering)`, `(shouting)`, `(in a hurry tone)`

### QA Notes

- 2026-05-08: Fixed S1-mini tokenizer loading for checkpoints that use `tokenizer.tiktoken` + `special_tokens.json`.
- 2026-05-08: Fixed stale process detection in `start_fish_speech.sh`; it now requires the expected checkpoint path and a listening port.
- 2026-05-08: Fixed persistent output handling by saving Gradio results to `~/ai_generated/fish-speech/` and launching with `allowed_paths`.
- 2026-05-14: Fish Speech S2-Pro retest reached `Loading model from /srv/containers/edq/projects/fish-speech/checkpoints/s2-pro`, then the system later logged a global OOM kill of the Python process (~16GB RSS). Do not continue S2-Pro dashboard testing on this host without a lighter model, quantization/offload strategy, or a hard memory guard.
- Current status: starts successfully on S1-mini, but generated smoke outputs were only 0.046s and did not audibly satisfy the prompt. Do not mark ready until the code/checkpoint compatibility issue is resolved.
- Failed smoke outputs retained for debugging:
  - `/home/edq/ai_generated/fish-speech/fish_speech_20260508_070801.wav`
  - `/home/edq/ai_generated/fish-speech/fish_speech_20260508_070821.wav`

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
- Model weights should be pre-cached; do not rely on a first-run download during a creative session
- Requires SoX (`sox`) for the local qwen-tts import path
- Launcher sets `NUMBA_CACHE_DIR=/tmp/numba-qwen3-tts` to avoid numba cache locator failures
- Three modes: TTS (speakers), Voice Clone, Voice Design
- Only one model loaded at a time for 16GB VRAM compatibility
- Switching tabs may reload models
- 9 predefined speakers: Aiden, Dylan, Eric, Ono_anna, Ryan, Serena, Sohee, Uncle_fu, Vivian
- Voice design: describe age, gender, tone, emotion, accent

### QA Notes

- 2026-05-08: Dashboard launch and short TTS smoke passed.
- Verified persistent output: `/home/edq/ai_generated/qwen3-tts/tts_20260508_064359.wav` (24kHz mono WAV, non-zero).
- Gradio 6 warning cleanup: `theme` is applied in `launch()`, not the `Blocks` constructor.

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
- Current Qwen3-TTS returns filepath outputs; audiobook assembly must accept persistent file paths as well as legacy `(sample_rate, array)` audio tuples

### QA Notes

- 2026-05-08: TXT preview and short audiobook conversion passed through the Dashboard.
- Verified persistent outputs:
  - `/home/edq/ai_generated/qwen3-audiobook/audiobook_20260508_065405.mp3` (24kHz mono MP3, non-zero)
  - `/home/edq/ai_generated/qwen3-audiobook/audiobook_20260508_065405.wav` (24kHz mono WAV, non-zero)
- Fixed final assembly failure caused by the Qwen3-TTS filepath return shape.

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

---

## VoxCPM2

**Port:** 8049
**Purpose:** 2B diffusion TTS with 48kHz output, voice design, and voice cloning

### Launch

```bash
cd /srv/containers/edq
bash scripts/start_voxcpm2.sh
```

**Access at:** `http://192.168.7.226:8049`

### Configuration

- **Script**: `scripts/voxcpm2_server.py`
- **Launcher**: `scripts/start_voxcpm2.sh`
- **Venv**: `venv_voxcpm2`
- **Output**: `~/ai_generated/voxcpm2/`

### Key Considerations

- Gradio must launch with `allowed_paths=[OUTPUT_DIR]`; otherwise generation succeeds but the UI/client rejects the persistent file path.
- Launcher must be executable.

### QA Notes

- 2026-05-07: Dashboard launch and short TTS smoke passed.
- Verified persistent output: `/home/edq/ai_generated/voxcpm2/voxcpm2_20260507_212733.wav` (48kHz mono WAV, non-zero).

---

## Dragon Audio Workstation

**Port:** 8026
**Purpose:** Audio enhancement, stem separation, dereverb, transcription, and waveform tools

### Launch

```bash
cd /srv/containers/edq
bash scripts/start_audio_tools_native.sh
```

**Access at:** `http://192.168.7.226:8026`

### Configuration

- **Launcher**: `scripts/start_audio_tools_native.sh`
- **Output**: `~/ai_generated/audio-tools/`

### QA Notes

- 2026-05-08: Dashboard launch and `/api/enhance` smoke passed using a VoxCPM2 WAV input.
- Verified persistent output: `/home/edq/ai_generated/audio-tools/enhanced_20260508_064124.wav` (48kHz mono WAV, non-zero).
- `/audio/<file>` supports GET; HEAD returns 405, so use GET/ranged GET for automated file availability checks.

---

## TADA TTS

**Port:** 8037
**Purpose:** Hume TADA generative TTS with voice cloning and token alignment

### Launch

```bash
cd /srv/containers/edq
bash scripts/start_tada.sh
```

**Access at:** `http://192.168.7.226:8037`

### Configuration

- **Script**: `scripts/tada_gradio.py`
- **Launcher**: `scripts/start_tada.sh`
- **Venv**: `venv_tada`
- **Output**: `~/ai_generated/tada/`

### Key Considerations

- Launcher sets `NUMBA_CACHE_DIR=/tmp/numba-tada`.
- Gradio must launch with `allowed_paths=[str(OUTPUT_DIR)]`; otherwise persistent outputs can be blocked by Gradio path validation.
- `descript-audio-codec` is required for the `dac.*` imports.
- `transformers==4.57.6` with `huggingface_hub==0.36.0` avoids the `all_tied_weights_keys` failure observed with Transformers 5.x.

### Current Blocker

- 2026-05-08: Runtime smoke is blocked by gated upstream access to `meta-llama/Llama-3.2-1B` (HTTP 403). Do not mark ready until the gated model is accessible or the app is reconfigured to a local/ungated model.
