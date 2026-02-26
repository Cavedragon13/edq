# Gradio → Native UI Migration Plan

**Principle:** The Python model/inference code is fine in every case. What's being replaced is only the Gradio wrapper — it gets swapped for a FastAPI backend + native HTML/JS frontend.

**Pattern for every migration:**
1. Extract inference functions (unchanged) into new `*_server.py`
2. Expose via `POST /api/process` (multipart for files, JSON for config)
3. Serve results as file downloads or JSON with base64/path
4. New HTML/JS frontend, same venv

**Risk strategy:** Each migrated service runs on **port +100** during development. Old Gradio version stays alive and untouched. Side-by-side test before retiring old version.

---

## Priority Order

| # | Service | Port | Lines | Complexity | Main Gain |
|---|---------|------|-------|------------|-----------|
| 1 | Rembg | 8012 | 173 | Simple | Transparency checkerboard, before/after toggle |
| 2 | Real-ESRGAN | 8010 | 353 | Low | Before/after comparison slider |
| 3 | Dolphin Vision | 8025 | 275 | Medium | Proper chat bubbles + streaming feel |
| 4 | Audio Processing Suite | 8026 | 339 | Medium | Waveform display, side-by-side original/processed |
| 5 | Qwen3-Audiobook | 8014 | 482 | Hard | Chapter nav, per-chapter players, progress tracking |

---

## 1 — Rembg (8012) — Simple

**The issue:** Gradio's image output doesn't handle transparency well. You can't see whether the mask cut cleanly at the edges — the output looks like a white-background image until you save it.

**What the native UI adds:**
- Output previewed on a checkerboard background (transparency is visible immediately)
- Before/after toggle (click to flip between original and removed)
- One-click PNG download (with alpha, not flattened)
- Optional: paint-to-restore brush for edge cleanup

**Backend change:** `rembg_gradio.py` has 3 functions. The core is ~20 lines. FastAPI endpoint: `POST /api/remove` → returns PNG as binary.

**New frontend:** Single page, drag-drop zone, instant preview on checkerboard. Simplest of the five.

**Dev port:** 8112 → retire 8012 after approval.

---

## 2 — Real-ESRGAN (8010) — Low

**The issue:** No comparison between original and upscaled — you're guessing whether it actually improved. Gradio's image display also doesn't show dimensions clearly.

**What the native UI adds:**
- CSS drag-handle comparison slider (left = original, right = upscaled)
- Dimension readout before/after (e.g., 512×512 → 2048×2048)
- Model selector stays, face enhancement toggle stays
- Download button with filename that includes the model used

**Backend change:** 4 functions, all inference. FastAPI: `POST /api/upscale` with model/face params → returns image path.

**Note:** Real-ESRGAN is GPU, so results take time. The native UI can show a real progress indicator rather than Gradio's spinner.

**Dev port:** 8110 → retire 8010 after approval.

---

## 3 — Dolphin Vision (8025) — Medium

**The issue:** Gradio's Chatbot component renders multi-turn conversation awkwardly when images are in the thread. The "uncensored" nature means you sometimes get long responses — Gradio truncates or wraps them badly.

**What the native UI adds:**
- Proper chat bubble layout (image thumbnails inline in your message)
- Token streaming (characters appear as they generate, not all at once)
- Copy button on each response
- Image drag-drop into the chat input
- Clear conversation button

**Backend change:** The model is loaded once at startup. Inference is a single generation call. FastAPI: `POST /api/chat` with image (optional) + message history → SSE stream for token-by-token response.

**Note:** This is the only one that benefits from streaming. Requires adding SSE to the backend (EventSourceResponse from `sse-starlette`).

**Dev port:** 8125 → retire 8025 after approval.

---

## 4 — Audio Processing Suite (8026) — Medium

**The issue:** Three tools (karaoke stems, vocal dereverb, ASR), but Gradio's tabs mean you can't see what's happening. No waveform — you upload and wait and hope. The stems output in particular needs waveform confirmation you separated correctly before you commit to downloading.

**What the native UI adds:**
- Waveform display for uploaded file (Web Audio API, no server needed)
- After processing: side-by-side waveforms (original + each stem)
- Inline playback for all outputs (vocal, instrumental, dereverbed)
- ASR tab gets a proper transcript display with copy and timestamp toggle
- All three tools on one page, not behind tabs

**Backend change:** 6 functions across the three tools. All file-in / file-out. FastAPI: three endpoints (`/api/karaoke`, `/api/dereverb`, `/api/asr`). The model loading from SoulX paths is unchanged.

**Dev port:** 8126 → retire 8026 after approval.

---

## 5 — Qwen3-Audiobook (8014) — Hard

**The issue:** Converts a whole document to audio but presents it as one long task with a spinner. You can't preview chapter 3 without waiting for chapters 1-2. No way to re-generate just a chapter. No sense of where you are in the document.

**What the native UI adds:**
- Document upload → parse into chapters/sections (visible in sidebar)
- Generate chapter-by-chapter with individual progress
- Each completed chapter gets its own audio player (play, seek, download)
- Regenerate individual chapters (e.g., if TTS voice was wrong)
- Speaker selector per-chapter (if you want different voices for different sections)
- Final "Download All as ZIP" when complete

**Backend change:** 8 functions, most around document parsing and TTS HTTP calls to port 8009. Requires more careful API design — chapter state needs to persist between requests. Use a simple in-memory job dict (or SQLite if paranoid).

**This is a meaningful rewrite of the UI logic, not just a wrapper swap.**

**Dev port:** 8114 → retire 8014 after approval.

---

## Shared Notes

**What doesn't change in any case:**
- The venv (all dependencies stay the same)
- Model file paths
- Output directory (`~/ai_generated/...`)
- The inference code itself

**What always changes:**
- `gr.Blocks` → FastAPI app
- Gradio components → HTML form elements + fetch() calls
- Gradio file I/O → multipart POST + file response

**New dependency** (all migrations): `fastapi`, `uvicorn`, `python-multipart` — these are tiny and already present in most venvs.

**For Dolphin Vision only:** `sse-starlette` for streaming.

---

*Plan written 2026-02-19. Tackle in order — each is independent.*
