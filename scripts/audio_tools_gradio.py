#!/usr/bin/env python3
"""
Audio Processing Suite - Gradio Interface
Three powerful audio tools from the SoulX-Singer preprocessing pipeline:

Tab 1: Karaoke Maker - Separate vocals from instrumental
Tab 2: Vocal Dereverb - Remove reverb from vocals
Tab 3: Speech-to-Text - Transcribe audio in EN/ZH/YUE

Reuses venv_soulxsinger (all deps included).
"""

import sys
import os
import gradio as gr
import numpy as np
import tempfile
import soundfile as sf
from pathlib import Path
from datetime import datetime

# Add SoulX-Singer project to path for preprocess imports
SOULX_PROJECT = "/srv/containers/edq/projects/SoulX-Singer"
if SOULX_PROJECT not in sys.path:
    sys.path.insert(0, SOULX_PROJECT)

# Model paths (symlinked to /srv/containers/edq/models/SoulX-Singer-Preprocess/)
PREPROCESS_BASE = "/srv/containers/edq/models/SoulX-Singer-Preprocess"
SEP_MODEL = f"{PREPROCESS_BASE}/mel-band-roformer-karaoke/mel_band_roformer_karaoke_becruily.ckpt"
SEP_CONFIG = f"{PREPROCESS_BASE}/mel-band-roformer-karaoke/config_karaoke_becruily.yaml"
DER_MODEL = f"{PREPROCESS_BASE}/dereverb_mel_band_roformer/dereverb_mel_band_roformer_anvuew_sdr_19.1729.ckpt"
DER_CONFIG = f"{PREPROCESS_BASE}/dereverb_mel_band_roformer/dereverb_mel_band_roformer_anvuew.yaml"
ZH_MODEL = f"{PREPROCESS_BASE}/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
EN_MODEL = f"{PREPROCESS_BASE}/parakeet-tdt-0.6b-v2/parakeet-tdt-0.6b-v2.nemo"

OUTPUT_DIR = Path(os.path.expanduser("~/ai_generated/audio-tools"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Lazy-loaded models
_separator = None
_transcriber = None


def get_separator():
    """Lazy-load VocalSeparator."""
    global _separator
    if _separator is not None:
        return _separator, None
    try:
        from preprocess.tools import VocalSeparator
        print("Loading vocal separation models...")
        _separator = VocalSeparator(
            sep_model_path=SEP_MODEL,
            sep_config_path=SEP_CONFIG,
            der_model_path=DER_MODEL,
            der_config_path=DER_CONFIG,
            device="cuda",
            verbose=True
        )
        print("Vocal separation models loaded!")
        return _separator, None
    except Exception as e:
        import traceback
        return None, f"Error loading separator: {e}\n{traceback.format_exc()}"


def get_transcriber():
    """Lazy-load LyricTranscriber."""
    global _transcriber
    if _transcriber is not None:
        return _transcriber, None
    try:
        from preprocess.tools import LyricTranscriber
        print("Loading ASR models (Chinese)...")
        _transcriber = LyricTranscriber(
            zh_model_path=ZH_MODEL,
            en_model_path=EN_MODEL,
            device="cuda",
            verbose=True
        )
        print("ASR models loaded!")
        return _transcriber, None
    except Exception as e:
        import traceback
        return None, f"Error loading transcriber: {e}\n{traceback.format_exc()}"


def timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


# --- Tab 1: Karaoke Maker ---

def make_karaoke(audio_file):
    """Separate vocals from instrumental."""
    if audio_file is None:
        return None, None, "Please upload an audio file."

    separator, err = get_separator()
    if err:
        return None, None, f"Failed to load model:\n{err}"

    try:
        result = separator.process(audio_file)
        ts = timestamp()

        # Save vocals
        vocals_path = str(OUTPUT_DIR / f"vocals_{ts}.wav")
        sf.write(vocals_path, result.vocals.T, result.sample_rate)

        # Save instrumental (accompaniment)
        instrumental_path = str(OUTPUT_DIR / f"instrumental_{ts}.wav")
        sf.write(instrumental_path, result.accompaniment.T, result.sample_rate)

        status = (
            f"✓ Separation complete!\n"
            f"  Sample rate: {result.sample_rate} Hz\n"
            f"  Vocals: {vocals_path}\n"
            f"  Instrumental: {instrumental_path}"
        )
        return vocals_path, instrumental_path, status

    except Exception as e:
        import traceback
        return None, None, f"Error: {e}\n{traceback.format_exc()}"


# --- Tab 2: Vocal Dereverb ---

def dereverb_audio(audio_file):
    """Remove reverb from vocals."""
    if audio_file is None:
        return None, "Please upload an audio file."

    separator, err = get_separator()
    if err:
        return None, f"Failed to load model:\n{err}"

    try:
        result = separator.process(audio_file)
        ts = timestamp()

        # Save dry (dereverbed) vocals
        dry_path = str(OUTPUT_DIR / f"dry_vocals_{ts}.wav")
        sf.write(dry_path, result.vocals_dereverbed.T, result.sample_rate)

        status = (
            f"✓ Dereverb complete!\n"
            f"  Sample rate: {result.sample_rate} Hz\n"
            f"  Output: {dry_path}"
        )
        return dry_path, status

    except Exception as e:
        import traceback
        return None, f"Error: {e}\n{traceback.format_exc()}"


# --- Tab 3: Speech-to-Text ---

def transcribe_audio(audio_file, language):
    """Transcribe audio to text with timestamps."""
    if audio_file is None:
        return "Please upload an audio file."

    transcriber, err = get_transcriber()
    if err:
        return f"Failed to load model:\n{err}"

    try:
        # Map UI language name to transcriber format
        lang_map = {
            "Mandarin (Chinese)": "Mandarin",
            "Cantonese": "Cantonese",
            "English": "English",
        }
        lang = lang_map.get(language, "Mandarin")

        # If file is not wav, convert it
        input_path = audio_file
        if not audio_file.endswith(".wav"):
            import librosa
            audio, sr = librosa.load(audio_file, sr=16000, mono=True)
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            sf.write(tmp.name, audio, sr)
            input_path = tmp.name

        words, durs = transcriber.process(input_path, language=lang)

        # Format as readable transcript with rough timestamps
        lines = []
        current_time = 0.0
        current_line = []
        line_start = 0.0

        for word, dur in zip(words, durs):
            if word == "<SP>":
                if current_line:
                    end_time = current_time + dur
                    lines.append(f"[{line_start:.1f}s - {end_time:.1f}s] {' '.join(current_line)}")
                    current_line = []
                    line_start = end_time
            else:
                if not current_line:
                    line_start = current_time
                current_line.append(word)
            current_time += dur

        if current_line:
            lines.append(f"[{line_start:.1f}s - {current_time:.1f}s] {' '.join(current_line)}")

        transcript = "\n".join(lines) if lines else "(No speech detected)"
        return transcript

    except Exception as e:
        import traceback
        return f"Error: {e}\n{traceback.format_exc()}"


# --- Gradio UI ---

CUSTOM_CSS = """
body { background-color: #1e1e1e; }
.gradio-container { background-color: #1e1e1e !important; }
"""

with gr.Blocks(title="Audio Processing Suite") as demo:
    gr.Markdown(
        """
        # 🎵 Audio Processing Suite
        Professional audio tools powered by SoulX-Singer preprocessing models.
        *Models load on first use (~2-4GB VRAM per tab).*
        """
    )

    with gr.Tab("🎤 Karaoke Maker"):
        gr.Markdown(
            "**Separate vocals from instrumental** using mel-band-roformer (1.7GB model). "
            "Outputs both vocal stem and instrumental track."
        )
        with gr.Row():
            with gr.Column():
                karaoke_input = gr.Audio(
                    label="Upload Song",
                    type="filepath",
                    sources=["upload"]
                )
                karaoke_btn = gr.Button("🎤 Separate Vocals", variant="primary", size="lg")

            with gr.Column():
                karaoke_vocals = gr.Audio(label="Vocals", type="filepath")
                karaoke_instrumental = gr.Audio(label="Instrumental", type="filepath")
                karaoke_status = gr.Textbox(label="Status", lines=4, interactive=False)

        karaoke_btn.click(
            fn=make_karaoke,
            inputs=[karaoke_input],
            outputs=[karaoke_vocals, karaoke_instrumental, karaoke_status],
            show_progress=True
        )

    with gr.Tab("🎙️ Vocal Dereverb"):
        gr.Markdown(
            "**Remove room reverb from vocals** using dereverb-mel-band-roformer (871MB model). "
            "Clean up reverby vocals for remixing or rerecording."
        )
        with gr.Row():
            with gr.Column():
                dereverb_input = gr.Audio(
                    label="Upload Vocal",
                    type="filepath",
                    sources=["upload"]
                )
                dereverb_btn = gr.Button("🎙️ Remove Reverb", variant="primary", size="lg")

            with gr.Column():
                dereverb_output = gr.Audio(label="Dry Vocals", type="filepath")
                dereverb_status = gr.Textbox(label="Status", lines=3, interactive=False)

        dereverb_btn.click(
            fn=dereverb_audio,
            inputs=[dereverb_input],
            outputs=[dereverb_output, dereverb_status],
            show_progress=True
        )

    with gr.Tab("📝 Speech-to-Text"):
        gr.Markdown(
            "**Transcribe speech with word-level timestamps.** "
            "English uses NeMo Parakeet-TDT (2.4GB), Chinese/Cantonese uses FunASR Paraformer (953MB)."
        )
        with gr.Row():
            with gr.Column():
                asr_input = gr.Audio(
                    label="Upload Audio",
                    type="filepath",
                    sources=["upload"]
                )
                asr_language = gr.Dropdown(
                    label="Language",
                    choices=["Mandarin (Chinese)", "Cantonese", "English"],
                    value="Mandarin (Chinese)"
                )
                asr_btn = gr.Button("📝 Transcribe", variant="primary", size="lg")

            with gr.Column():
                asr_output = gr.Textbox(
                    label="Transcript",
                    lines=20,
                    interactive=False,
                    placeholder="Transcript will appear here with timestamps..."
                )

        asr_btn.click(
            fn=transcribe_audio,
            inputs=[asr_input, asr_language],
            outputs=[asr_output],
            show_progress=True
        )


if __name__ == "__main__":
    print("=" * 50)
    print("Audio Processing Suite")
    print(f"SoulX project: {SOULX_PROJECT}")
    print(f"Models: {PREPROCESS_BASE}")
    print(f"Outputs: {OUTPUT_DIR}")
    print("=" * 50)
    print("")
    print("Models load on first use per tab.")
    print("")

    demo.launch(
        server_name="0.0.0.0",
        server_port=8026,
        share=False,
        theme=gr.themes.Soft(),
        css=CUSTOM_CSS
    )
