# Vision AI Services

## Dragonsight 4

**Port:** 8080
**Purpose:** Drag-and-drop image analysis, AI descriptions, smart file naming

### Launch
```bash
cd /srv/containers/edq
bash scripts/start_dragonsight.sh
```

**Access at:** `http://192.168.7.226:8080/media/dragonsight4.html`

### Configuration
- **HTML App**: `media/dragonsight4.html`
- **Launcher**: `scripts/start_dragonsight.sh`
- **Primary Backend**: Ollama (always-on via snap)
  - `qwen3-vl:8b` (default, 6.1GB)
  - `llama3.2-vision:11b` (optional, 7.8GB)
- **Secondary Backend**: LM Studio (manual start)
  - GLM-4.6V with Dolphin uncensored prompt

### Features
- Pure frontend (HTML/JS) - no Python backend needed
- Model selector for Ollama VLMs
- Automatic fallback between backends
- Clipboard paste support (Ctrl+V)
- Parallel API calls for faster results
- Copy buttons for all outputs
- Metadata JSON download

### Backend URLs
- Ollama: `http://127.0.0.1:8080/api/ollama/generate` → proxied to `127.0.0.1:11434`
- LM Studio: `http://localhost:1234/v1/chat/completions` (direct, same-origin not needed)

### Architecture
Frontend served on 8080, Ollama calls proxied through same port (see [Architecture Patterns](../architecture-patterns.md))

### Key Considerations
- **Ollama is always-on** via snap - no manual start needed
- Default model: qwen3-vl:8b, optional: llama3.2-vision:11b
- Pure HTML/JS frontend - no Python dependencies
- LM Studio available as secondary backend (manual start) for uncensored GLM-4.6V

---

## SAM 2.1 (Segment Anything)

**Port:** 8005
**Purpose:** Meta's foundation model for image and video segmentation

### Launch
```bash
cd /srv/containers/edq
bash scripts/start_sam2.sh
```

**Access at:** `http://192.168.7.226:8005`

### Configuration
- **Location**: `projects/sam2/`
- **Launcher**: `scripts/start_sam2.sh`
- **Venv**: `venv_sam2`
- **Requirements**: ~6GB VRAM

### Features
- Click-to-segment in images
- Track objects across video frames
- Automatic mask generation
- Point and box prompts

### Key Considerations
- Click on image to segment objects
- Supports video tracking (propagate mask across frames)
- First launch downloads ~2.5GB checkpoint
- ~6GB VRAM for large model

---

## LivePortrait (Portrait Animation)

**Port:** 8006
**Purpose:** KlingTeam's portrait animation with expression transfer

### Launch
```bash
cd /srv/containers/edq
bash scripts/start_liveportrait.sh
```

**Access at:** `http://192.168.7.226:8006`

### Configuration
- **Location**: `projects/LivePortrait/`
- **Launcher**: `scripts/start_liveportrait.sh`
- **Venv**: `venv_liveportrait`
- **Requirements**: ~6GB VRAM

### Features
- Image to animated portrait
- Video-driven face animation
- Expression transfer from driving video
- Animals mode (cats & dogs)

### Key Considerations
- Upload source portrait + driving video
- First launch downloads ~2GB of model weights
- Use short driving videos (2-5 seconds) for best results
- Animals mode available for cats & dogs
- Expression transfer works best with similar face angles
