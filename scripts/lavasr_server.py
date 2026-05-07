#!/usr/bin/env python3
"""
LavaSR - Speech Enhancement & Audio Upsampling
Port 8034 | Part of Dragonsuite

Enhances speech audio: removes noise, upsamples to 48kHz.
~500MB VRAM | ~50MB model | 5000x realtime on GPU
"""

import os
import sys
import tempfile
import traceback
from pathlib import Path

import gradio as gr
import torch
import torchaudio
import soundfile as sf
import numpy as np

PORT = 8034
MODEL_ID = "YatharthS/LavaSR"

# ── Model loading ──────────────────────────────────────────────────────────────

model = None
model_device = None

def load_model(device: str):
    global model, model_device
    if model is not None and model_device == device:
        return model
    from LavaSR.model import LavaEnhance2
    print(f"   Loading LavaSR on {device}...")
    model = LavaEnhance2(model_path=MODEL_ID, device=device)
    model_device = device
    print("   ✓ LavaSR loaded")
    return model


# ── Processing ─────────────────────────────────────────────────────────────────

def enhance_audio(audio_path: str, denoise: bool, enhance_bwe: bool, device_choice: str) -> tuple:
    """Enhance audio file. Returns (output_path, status_message)."""
    if audio_path is None:
        return None, "❌ No audio file provided."

    device = "cuda" if device_choice == "GPU (CUDA)" and torch.cuda.is_available() else "cpu"

    try:
        m = load_model(device)

        # Load audio — LavaSR expects 16kHz mono tensor
        wav, sr = torchaudio.load(audio_path)
        if wav.shape[0] > 1:
            wav = wav.mean(dim=0, keepdim=True)  # stereo → mono
        if sr != 16000:
            wav = torchaudio.functional.resample(wav, sr, 16000)
        wav = wav.squeeze(0).to(device)

        # Enhance
        with torch.inference_mode():
            enhanced = m.enhance(wav, enhance=enhance_bwe, denoise=denoise, batch=True)

        # enhanced is a 1D tensor at 48kHz
        enhanced_np = enhanced.cpu().numpy()

        # Write to temp file
        suffix = Path(audio_path).suffix or ".wav"
        out_fd, out_path = tempfile.mkstemp(suffix=f"_lavasr{suffix}")
        os.close(out_fd)
        sf.write(out_path, enhanced_np, 48000)

        dur = len(enhanced_np) / 48000
        status = (
            f"✅ Enhanced — {dur:.1f}s at 48kHz\n"
            f"   Denoise: {'on' if denoise else 'off'} | BWE: {'on' if enhance_bwe else 'off'} | Device: {device}"
        )
        return out_path, status

    except Exception:
        return None, f"❌ Error:\n{traceback.format_exc()}"


# ── Gradio UI ──────────────────────────────────────────────────────────────────

def build_ui():
    cuda_available = torch.cuda.is_available()
    default_device = "GPU (CUDA)" if cuda_available else "CPU"
    device_choices = ["GPU (CUDA)", "CPU"] if cuda_available else ["CPU"]

    with gr.Blocks(
        title="LavaSR — Speech Enhancement",
        theme=gr.themes.Base(primary_hue="violet"),
        css="""
            body { background: #18181b; }
            .gradio-container { max-width: 860px !important; }
            footer { display: none !important; }
        """,
    ) as demo:
        gr.Markdown(
            """
# 🎙️ LavaSR — Speech Enhancement

Remove noise and upsample speech audio to **48kHz** using LavaSR.
Works on any speech audio 8–48kHz. Fast: ~5000× realtime on GPU.
            """
        )

        with gr.Row():
            with gr.Column(scale=2):
                audio_input = gr.Audio(
                    label="Input Audio",
                    type="filepath",
                    sources=["upload", "microphone"],
                )
                with gr.Row():
                    denoise_cb = gr.Checkbox(label="Denoise", value=True)
                    bwe_cb = gr.Checkbox(label="Bandwidth Extension (BWE)", value=True)
                device_dd = gr.Dropdown(
                    choices=device_choices,
                    value=default_device,
                    label="Device",
                )
                run_btn = gr.Button("✨ Enhance", variant="primary")

            with gr.Column(scale=2):
                audio_output = gr.Audio(label="Enhanced Output (48kHz)", type="filepath")
                status_box = gr.Textbox(
                    label="Status",
                    lines=3,
                    interactive=False,
                    placeholder="Output will appear here...",
                )

        run_btn.click(
            fn=enhance_audio,
            inputs=[audio_input, denoise_cb, bwe_cb, device_dd],
            outputs=[audio_output, status_box],
        )

        gr.Markdown(
            """
---
**Tips**
- Input can be any sample rate; it will be resampled to 16kHz internally before enhancement
- Output is always 48kHz mono
- Denoise uses UL-UNAS denoiser; BWE uses the neural bandwidth extender
- Both can be disabled independently to isolate effects
            """
        )

    return demo


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print()
    print("LavaSR — Speech Enhancement")
    print("============================")
    print(f"   Port:    {PORT}")
    print(f"   Local:   http://localhost:{PORT}")
    print(f"   LAN:     http://192.168.7.226:{PORT}")
    print(f"   CUDA:    {'✓ available' if torch.cuda.is_available() else '✗ not available (CPU mode)'}")
    print()
    print("Press Ctrl+C to stop")
    print()

    demo = build_ui()
    demo.launch(
        server_name="0.0.0.0",
        server_port=PORT,
        share=False,
    )


if __name__ == "__main__":
    main()
