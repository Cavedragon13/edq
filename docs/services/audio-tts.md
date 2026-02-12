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
