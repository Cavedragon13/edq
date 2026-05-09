#!/usr/bin/env python3
"""
TADA TTS - Hume AI open-source generative speech model
Voice cloning TTS with multilingual support (TADA-3B-ML)
Port 8037
"""

import os
import sys
import time
from pathlib import Path
from datetime import datetime

import torch
import torchaudio
import gradio as gr

# Output directory
OUTPUT_DIR = Path.home() / "ai_generated" / "tada"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba-tada")

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
SAMPLE_RATE = 24000  # TADA native output sample rate

LANGUAGES = {
    "English (default)": None,
    "Arabic": "ar",
    "Chinese": "ch",
    "German": "de",
    "Spanish": "es",
    "French": "fr",
    "Italian": "it",
    "Japanese": "ja",
    "Polish": "pl",
    "Portuguese": "pt",
}

# Lazy-loaded globals
_model = None
_encoder_cache = {}  # language_key -> Encoder instance


def load_model():
    global _model
    if _model is None:
        from tada.modules.tada import TadaForCausalLM
        print("Loading TADA-3B-ML model (may take ~30s on first load)...")
        _model = TadaForCausalLM.from_pretrained("HumeAI/tada-3b-ml").to(DEVICE)
        _model.eval()
        print("Model loaded.")
    return _model


def load_encoder(language_code=None):
    key = language_code or "en"
    if key not in _encoder_cache:
        from tada.modules.encoder import Encoder
        kwargs = {"subfolder": "encoder"}
        if language_code:
            kwargs["language"] = language_code
        print(f"Loading encoder (language={key})...")
        enc = Encoder.from_pretrained("HumeAI/tada-codec", **kwargs).to(DEVICE)
        enc.eval()
        _encoder_cache[key] = enc
    return _encoder_cache[key]


def generate_speech(reference_audio_path, text, language_label, num_extra_steps):
    if not reference_audio_path:
        return None, "❌ Please upload a reference audio file."
    if not text.strip():
        return None, "❌ Please enter text to synthesize."

    try:
        language_code = LANGUAGES.get(language_label)
        model = load_model()
        encoder = load_encoder(language_code)

        # Load reference audio
        audio, sr = torchaudio.load(reference_audio_path)
        audio = audio.to(DEVICE)

        # Encode reference
        with torch.no_grad():
            prompt = encoder(audio, text=[text], sample_rate=sr)

        # Generate
        with torch.no_grad():
            output = model.generate(
                prompt=prompt,
                text=text,
                num_extra_steps=int(num_extra_steps),
            )

        # Extract first audio result
        if not output.audio or output.audio[0] is None:
            return None, "❌ Generation failed — model returned no audio."

        wav = output.audio[0].cpu()
        if wav.dim() == 1:
            wav = wav.unsqueeze(0)  # (1, samples) for torchaudio.save

        # Save to output dir
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = OUTPUT_DIR / f"tada_{ts}.wav"
        torchaudio.save(str(out_path), wav, SAMPLE_RATE)

        duration = wav.shape[-1] / SAMPLE_RATE
        return str(out_path), f"✅ Generated {duration:.1f}s of audio → {out_path.name}"

    except Exception as e:
        return None, f"❌ Error: {e}"


# --- Gradio UI ---

DARK_CSS = """
body, .gradio-container { background: #1a1a2e !important; color: #e0e0e0 !important; }
.gr-button { background: #2d2d2d !important; color: #e0e0e0 !important; border: 1px solid #4a5568 !important; }
.gr-button.primary { background: #4a3f8c !important; }
.gr-button:hover { filter: brightness(1.2); }
.gr-box, .gr-panel, .gr-form { background: #2d2d2d !important; border-color: #4a5568 !important; }
label, .gr-block-label { color: #9ca3af !important; }
input, textarea, select { background: #1e1e1e !important; color: #e0e0e0 !important; border-color: #4a5568 !important; }
.gr-prose { color: #e0e0e0 !important; }
footer { display: none !important; }
"""

with gr.Blocks(title="TADA TTS") as demo:
    gr.Markdown("# 🎙️ TADA TTS\n*Hume AI — Generative voice cloning with multilingual support*")

    with gr.Row():
        with gr.Column(scale=1):
            ref_audio = gr.Audio(
                label="Reference Audio (sets the voice)",
                type="filepath",
                sources=["upload", "microphone"],
            )
            language_dd = gr.Dropdown(
                label="Output Language",
                choices=list(LANGUAGES.keys()),
                value="English (default)",
            )
            extra_steps = gr.Slider(
                label="Extra continuation steps",
                minimum=0, maximum=200, step=10, value=0,
                info="Adds speech continuation after text ends. 0 = disabled.",
            )

        with gr.Column(scale=2):
            text_input = gr.Textbox(
                label="Text to synthesize",
                placeholder="Enter the text you want TADA to speak...",
                lines=5,
            )
            generate_btn = gr.Button("🎙️ Generate", variant="primary")
            status_box = gr.Textbox(label="Status", interactive=False, lines=1)
            output_audio = gr.Audio(label="Output Audio", type="filepath")

    gr.Markdown(
        "**Notes:** TADA-3B-ML uses a reference audio to clone the voice. "
        "A 5–30 second reference works best. Encoder for non-English languages "
        "loads on first use (cached after that)."
    )

    generate_btn.click(
        fn=generate_speech,
        inputs=[ref_audio, text_input, language_dd, extra_steps],
        outputs=[output_audio, status_box],
    )

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=int(os.environ.get("GRADIO_SERVER_PORT", 8037)),
        allowed_paths=[str(OUTPUT_DIR)],
        show_error=True,
        css=DARK_CSS,
    )
