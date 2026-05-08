#!/usr/bin/env python3
"""VoxCPM2 TTS Server — 2B diffusion autoregressive, 48kHz, 30+ languages."""

import os
import sys
from datetime import datetime
import numpy as np
import soundfile as sf
import gradio as gr

MODEL_ID = "openbmb/VoxCPM2"
OUTPUT_DIR = os.path.expanduser("~/ai_generated/voxcpm2")
os.makedirs(OUTPUT_DIR, exist_ok=True)

model = None


def load_model():
    global model
    if model is not None:
        return
    print("Loading VoxCPM2...", flush=True)
    from voxcpm import VoxCPM
    model = VoxCPM.from_pretrained(MODEL_ID, load_denoiser=False)
    print("VoxCPM2 ready.", flush=True)


def generate_tts(text, mode, reference_audio, prompt_text, cfg_value, steps):
    load_model()
    if not text.strip():
        return None, "⚠️ Enter some text."

    try:
        kwargs = dict(cfg_value=float(cfg_value), inference_timesteps=int(steps))

        if mode == "TTS / Voice Design":
            wav = model.generate(text=text, **kwargs)

        elif mode == "Voice Clone":
            if reference_audio is None:
                return None, "⚠️ Upload a reference WAV for Voice Clone mode."
            wav = model.generate(text=text, reference_wav_path=reference_audio, **kwargs)

        elif mode == "Ultimate Clone (highest fidelity)":
            if reference_audio is None:
                return None, "⚠️ Upload a reference WAV for Ultimate Clone mode."
            if not prompt_text.strip():
                return None, "⚠️ Provide the transcript of the reference audio for Ultimate Clone."
            wav = model.generate(
                text=text,
                prompt_wav_path=reference_audio,
                prompt_text=prompt_text,
                reference_wav_path=reference_audio,
            )

        sr = model.tts_model.sample_rate
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = os.path.join(OUTPUT_DIR, f"voxcpm2_{ts}.wav")
        sf.write(out_path, wav, sr)
        duration = len(wav) / sr
        print(f"[voxcpm2] {mode} | {duration:.1f}s | {out_path}", flush=True)
        return out_path, f"✅ Done — {duration:.1f}s at {sr}Hz\n{out_path}"

    except Exception as e:
        print(f"[voxcpm2] ERROR: {e}", flush=True)
        return None, f"❌ {e}"


with gr.Blocks(title="VoxCPM2 TTS") as demo:
    gr.Markdown("# 🐉 VoxCPM2 TTS\n2B diffusion autoregressive · 48kHz · 30+ languages · Voice Design & Cloning")

    with gr.Row():
        with gr.Column(scale=2):
            text = gr.Textbox(
                label="Text",
                placeholder='Plain text, or use voice design: "(A young woman, gentle voice) Hello!"',
                lines=4,
            )
            mode = gr.Radio(
                ["TTS / Voice Design", "Voice Clone", "Ultimate Clone (highest fidelity)"],
                value="TTS / Voice Design",
                label="Mode",
            )
            reference_audio = gr.Audio(
                label="Reference Audio (Clone modes only)",
                type="filepath",
                visible=False,
            )
            prompt_text = gr.Textbox(
                label="Reference Audio Transcript (Ultimate Clone only)",
                placeholder="Exact words spoken in the reference audio...",
                visible=False,
            )
            with gr.Row():
                cfg_value = gr.Slider(1.0, 5.0, value=2.0, step=0.5, label="CFG Scale")
                steps = gr.Slider(5, 30, value=10, step=5, label="Inference Steps")
            btn = gr.Button("Generate", variant="primary")

        with gr.Column(scale=1):
            audio_out = gr.Audio(label="Output", type="filepath")
            status = gr.Textbox(label="Status", interactive=False)

    def update_visibility(m):
        show_ref = m in ("Voice Clone", "Ultimate Clone (highest fidelity)")
        show_transcript = m == "Ultimate Clone (highest fidelity)"
        return gr.update(visible=show_ref), gr.update(visible=show_transcript)

    mode.change(update_visibility, inputs=mode, outputs=[reference_audio, prompt_text])

    btn.click(
        generate_tts,
        inputs=[text, mode, reference_audio, prompt_text, cfg_value, steps],
        outputs=[audio_out, status],
    )

    gr.Markdown("""
**Voice Design** — describe voice in parentheses: `(elderly man, raspy voice)` or `(cheerful child)`
**Voice Clone** — upload a reference WAV (any length, 16kHz preferred)
**Ultimate Clone** — highest fidelity; also provide the exact transcript of the reference audio
**Languages** — auto-detected: EN, ZH, JA, KO, FR, DE, ES, PT, AR, HI, and 20+ more + 9 Chinese dialects
    """)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8049))
    print(f"Starting VoxCPM2 on port {port}...", flush=True)
    print(f"Output directory: {OUTPUT_DIR}", flush=True)
    demo.launch(
        server_name="0.0.0.0",
        server_port=port,
        share=False,
        theme=gr.themes.Base(),
        allowed_paths=[OUTPUT_DIR],
        show_error=True,
    )
