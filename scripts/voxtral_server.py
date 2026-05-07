#!/usr/bin/env python3
"""
Voxtral TTS — Gradio web UI (port 8042)
Proxies to vLLM-Omni backend serving mistralai/Voxtral-4B-TTS-2603 on port 9042.
"""

import io
import os
import tempfile

import gradio as gr
import httpx
import numpy as np
import soundfile as sf

BACKEND_URL = os.environ.get("VOXTRAL_BACKEND_URL", "http://127.0.0.1:9042")
MODEL_ID = "mistralai/Voxtral-4B-TTS-2603"
PORT = int(os.environ.get("VOXTRAL_PORT", 8042))

# All 20 preset voices from the official model card
VOICES = [
    # English
    "casual_male", "casual_female", "cheerful_female", "neutral_male", "neutral_female",
    # French
    "fr_male", "fr_female",
    # Spanish
    "es_male", "es_female",
    # German
    "de_male", "de_female",
    # Italian
    "it_male", "it_female",
    # Portuguese
    "pt_male", "pt_female",
    # Dutch
    "nl_male", "nl_female",
    # Arabic
    "ar_male",
    # Hindi
    "hi_male", "hi_female",
]

FORMATS = ["wav", "mp3", "flac", "opus", "aac", "pcm"]


def generate_speech(text: str, voice: str, fmt: str, speed: float):
    if not text.strip():
        return None, "⚠️ Enter some text first."

    payload = {
        "input": text,
        "model": MODEL_ID,
        "voice": voice,
        "response_format": fmt,
        "speed": speed,
    }

    try:
        response = httpx.post(
            f"{BACKEND_URL}/v1/audio/speech",
            json=payload,
            timeout=120.0,
        )
        response.raise_for_status()
    except httpx.ConnectError:
        return None, "❌ Cannot connect to Voxtral backend on port 9042. Is the vLLM-Omni server running?"
    except httpx.HTTPStatusError as e:
        return None, f"❌ Backend error {e.response.status_code}: {e.response.text[:300]}"
    except Exception as e:
        return None, f"❌ {e}"

    audio_bytes = response.content
    size_kb = len(audio_bytes) / 1024

    # Parse audio for Gradio playback
    try:
        if fmt == "pcm":
            # Raw 16-bit PCM at 24kHz
            arr = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            audio_tuple = (24000, arr)
        else:
            arr, sr = sf.read(io.BytesIO(audio_bytes), dtype="float32")
            audio_tuple = (sr, arr)
    except Exception as e:
        # Fallback: save to temp file and return path
        suffix = f".{fmt}" if fmt != "pcm" else ".wav"
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        tmp.write(audio_bytes)
        tmp.flush()
        return tmp.name, f"✓ Generated {size_kb:.1f} KB (could not parse inline)"

    return audio_tuple, f"✓ {size_kb:.1f} KB · {voice} · {fmt} · {speed}x speed"


def check_backend():
    try:
        r = httpx.get(f"{BACKEND_URL}/health", timeout=3.0)
        if r.status_code == 200:
            return "🟢 Backend ready"
    except Exception:
        pass
    return "🔴 Backend not responding — start the vLLM-Omni server first"


with gr.Blocks(
    title="Voxtral TTS",
    theme=gr.themes.Soft(primary_hue="violet"),
    css="""
    body { background: #1a1a2e !important; }
    .gradio-container { background: #1a1a2e !important; max-width: 900px; margin: 0 auto; }
    """,
) as demo:
    gr.Markdown("# 🎙️ Voxtral TTS\n**mistralai/Voxtral-4B-TTS-2603** · 20 voices · 9 languages · 24 kHz")

    with gr.Row():
        with gr.Column(scale=3):
            text_input = gr.Textbox(
                label="Text",
                placeholder="Enter text to synthesize...",
                lines=5,
                max_lines=20,
            )
            with gr.Row():
                voice_dd = gr.Dropdown(
                    choices=VOICES,
                    value="casual_male",
                    label="Voice",
                )
                fmt_dd = gr.Dropdown(
                    choices=FORMATS,
                    value="wav",
                    label="Format",
                )
                speed_sl = gr.Slider(
                    minimum=0.25,
                    maximum=4.0,
                    value=1.0,
                    step=0.05,
                    label="Speed",
                )
            generate_btn = gr.Button("Generate Speech", variant="primary", size="lg")

        with gr.Column(scale=2):
            audio_out = gr.Audio(label="Output", type="numpy")
            status_box = gr.Textbox(label="Status", interactive=False, lines=2)
            backend_status = gr.Textbox(
                label="Backend",
                value=check_backend(),
                interactive=False,
            )
            refresh_btn = gr.Button("Refresh Backend Status", size="sm")

    generate_btn.click(
        fn=generate_speech,
        inputs=[text_input, voice_dd, fmt_dd, speed_sl],
        outputs=[audio_out, status_box],
    )
    refresh_btn.click(fn=check_backend, outputs=backend_status)

    with gr.Accordion("ℹ️ How emotion & style work in Voxtral", open=False):
        gr.Markdown("""
**Voxtral has no tag system.** Do not use `[laugh]`, SSML, or instruction prefixes — they will be spoken aloud as literal text.

**What actually controls output:**

| Control | Effect |
|---------|--------|
| **Voice preset** | Each voice has a baked-in character (casual, cheerful, neutral) |
| **Text content** | Punctuation and word choice have a weak emergent effect |
| **Speed slider** | Pacing — slower reads as more deliberate/serious |

**Text-side tips** (weak but real):
- Punctuation matters: `"Wait... really?!"` reads differently from `"Wait. Really."`
- Word choice carries weight: `"Absolutely incredible!"` vs `"Very good."`
- Short punchy sentences → urgency; long flowing sentences → calm

**For real emotion control**, use **Fish Speech (port 8003)** which supports inline tags like `[laugh]`, `[whispers]`, `[super happy]` at any point in the text.

Voice cloning (custom reference audio) is supported via the raw API on port 9042 — not exposed in this UI.
        """)
    gr.Markdown(
        "**Voices:** casual_male/female, cheerful_female, neutral_male/female (EN) · "
        "fr/es/de/it/pt/nl/hi male+female · ar_male"
    )


if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=PORT,
    )
