#!/usr/bin/env python3
"""Qwen3-TTS - Text-to-Speech with Voice Cloning and Voice Design
Local Gradio Interface for Dragonsuite

Features:
- TTS with predefined speakers
- Voice cloning from reference audio
- Voice design from natural language descriptions

Uses lazy loading to fit in 16GB VRAM.
"""

import os
import gc
import datetime
import numpy as np
import torch
import gradio as gr
import soundfile as sf

# Configuration
OUTPUT_DIR = os.path.expanduser("~/ai_generated/qwen3-tts")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba-qwen3-tts")

# Model cache - only one model loaded at a time for memory efficiency
_current_model = None
_current_model_type = None

# Available speakers for CustomVoice mode
SPEAKERS = [
    "Aiden", "Dylan", "Eric", "Ono_anna", "Ryan",
    "Serena", "Sohee", "Uncle_fu", "Vivian"
]

LANGUAGES = [
    "Auto", "Chinese", "English", "Japanese", "Korean",
    "French", "German", "Spanish", "Portuguese", "Russian"
]

# Determine device and dtype
if torch.cuda.is_available():
    DEVICE = "cuda"
    DTYPE = torch.bfloat16
    print(f"Using CUDA with bfloat16")
else:
    DEVICE = "cpu"
    DTYPE = torch.float32
    print(f"Using CPU with float32 (this will be slow)")


def get_model(model_type: str):
    """Get or load a model, unloading previous model if different type."""
    global _current_model, _current_model_type

    if _current_model is not None and _current_model_type == model_type:
        return _current_model

    # Unload current model
    if _current_model is not None:
        print(f"Unloading {_current_model_type} model...")
        del _current_model
        _current_model = None
        _current_model_type = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            print(f"CUDA memory after unload: {torch.cuda.memory_allocated() / 1024**3:.2f} GB")

    # Load new model
    from qwen_tts import Qwen3TTSModel

    model_id = f"Qwen/Qwen3-TTS-12Hz-1.7B-{model_type}"
    print(f"Loading {model_id}...")

    try:
        _current_model = Qwen3TTSModel.from_pretrained(
            model_id,
            device_map=DEVICE,
            dtype=DTYPE,
        )
        _current_model_type = model_type
        print(f"Model loaded. CUDA memory: {torch.cuda.memory_allocated() / 1024**3:.2f} GB")
        return _current_model
    except Exception as e:
        print(f"Error loading model: {e}")
        raise


def normalize_audio(wav, eps=1e-12):
    """Normalize audio to float32 in [-1, 1] range."""
    x = np.asarray(wav)
    if np.issubdtype(x.dtype, np.integer):
        info = np.iinfo(x.dtype)
        if info.min < 0:
            y = x.astype(np.float32) / max(abs(info.min), info.max)
        else:
            mid = (info.max + 1) / 2.0
            y = (x.astype(np.float32) - mid) / mid
    elif np.issubdtype(x.dtype, np.floating):
        y = x.astype(np.float32)
        m = np.max(np.abs(y)) if y.size else 0.0
        if m > 1.0 + 1e-6:
            y = y / (m + eps)
    else:
        raise TypeError(f"Unsupported dtype: {x.dtype}")

    y = np.clip(y, -1.0, 1.0)
    if y.ndim > 1:
        y = np.mean(y, axis=-1).astype(np.float32)
    return y


def audio_to_tuple(audio):
    """Convert Gradio audio input to (wav, sr) tuple."""
    if audio is None:
        return None
    if isinstance(audio, tuple) and len(audio) == 2:
        sr, wav = audio
        wav = normalize_audio(wav)
        return wav, int(sr)
    return None


def save_audio(wav, sr, prefix="qwen3tts"):
    """Save audio to output directory."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(OUTPUT_DIR, f"{prefix}_{timestamp}.wav")
    sf.write(output_path, wav, sr)
    return output_path


# ============ TTS (CustomVoice) ============
def generate_tts(text, language, speaker, instruct, progress=gr.Progress(track_tqdm=True)):
    """Generate speech using CustomVoice model with predefined speakers."""
    if not text or not text.strip():
        raise gr.Error("Please enter some text!")
    if not speaker:
        raise gr.Error("Please select a speaker!")

    try:
        tts = get_model("CustomVoice")

        with torch.no_grad():
            wavs, sr = tts.generate_custom_voice(
                text=text.strip(),
                language=language if language != "Auto" else None,
                speaker=speaker.lower().replace(" ", "_"),
                instruct=instruct.strip() if instruct and instruct.strip() else None,
                non_streaming_mode=True,
                max_new_tokens=4096,
            )

        output_path = save_audio(wavs[0], sr, "tts")
        print(f"TTS generated: {output_path}")
        return (sr, wavs[0]), output_path

    except Exception as e:
        raise gr.Error(f"Generation failed: {e}")


# ============ Voice Clone ============
def generate_voice_clone(ref_audio, ref_text, target_text, language, use_xvector_only,
                         progress=gr.Progress(track_tqdm=True)):
    """Clone voice from reference audio."""
    if not target_text or not target_text.strip():
        raise gr.Error("Please enter target text!")

    audio_tuple = audio_to_tuple(ref_audio)
    if audio_tuple is None:
        raise gr.Error("Please provide reference audio!")

    if not use_xvector_only and (not ref_text or not ref_text.strip()):
        raise gr.Error("Reference text is required unless 'x-vector only' is enabled!")

    try:
        tts = get_model("Base")

        with torch.no_grad():
            wavs, sr = tts.generate_voice_clone(
                text=target_text.strip(),
                language=language if language != "Auto" else None,
                ref_audio=audio_tuple,
                ref_text=ref_text.strip() if ref_text and not use_xvector_only else None,
                x_vector_only_mode=use_xvector_only,
                max_new_tokens=4096,
            )

        output_path = save_audio(wavs[0], sr, "clone")
        print(f"Voice clone generated: {output_path}")
        return (sr, wavs[0]), output_path

    except Exception as e:
        raise gr.Error(f"Voice cloning failed: {e}")


# ============ Voice Design ============
def generate_voice_design(text, language, voice_description, progress=gr.Progress(track_tqdm=True)):
    """Create custom voice using natural language description."""
    if not text or not text.strip():
        raise gr.Error("Please enter some text!")
    if not voice_description or not voice_description.strip():
        raise gr.Error("Please describe the voice!")

    try:
        tts = get_model("VoiceDesign")

        with torch.no_grad():
            wavs, sr = tts.generate_voice_design(
                text=text.strip(),
                language=language if language != "Auto" else None,
                instruct=voice_description.strip(),
                non_streaming_mode=True,
                max_new_tokens=4096,
            )

        output_path = save_audio(wavs[0], sr, "design")
        print(f"Voice design generated: {output_path}")
        return (sr, wavs[0]), output_path

    except Exception as e:
        raise gr.Error(f"Voice design failed: {e}")


# ============ Gradio UI ============
with gr.Blocks(
    title="Qwen3-TTS",
) as demo:
    gr.Markdown(
        """
        # Qwen3-TTS

        **Text-to-Speech** with Voice Cloning and Voice Design powered by
        [Qwen3-TTS](https://huggingface.co/collections/Qwen/qwen3-tts) (1.7B models).

        - **TTS**: Generate speech with 9 predefined voices + style control
        - **Voice Clone**: Clone any voice from a reference audio sample
        - **Voice Design**: Create new voices from natural language descriptions
        """
    )

    gr.Textbox(
        label="Output Directory",
        value=OUTPUT_DIR,
        interactive=False,
        info="Generated audio files are saved here",
    )

    with gr.Tabs():
        # ============ Tab 1: TTS ============
        with gr.Tab("TTS (Speakers)"):
            gr.Markdown("### Text-to-Speech with Predefined Speakers")

            with gr.Row():
                with gr.Column(scale=2):
                    tts_text = gr.Textbox(
                        label="Text to Synthesize",
                        lines=5,
                        placeholder="Enter text to convert to speech...",
                        value="Hello! Welcome to Qwen3 Text-to-Speech. This is a demonstration of high-quality neural speech synthesis.",
                    )

                    with gr.Row():
                        tts_language = gr.Dropdown(
                            label="Language",
                            choices=LANGUAGES,
                            value="Auto",
                        )
                        tts_speaker = gr.Dropdown(
                            label="Speaker",
                            choices=SPEAKERS,
                            value="Ryan",
                        )

                    tts_instruct = gr.Textbox(
                        label="Style / Emotion Instruction (Optional)",
                        lines=2,
                        placeholder="e.g., Very happy. · Whispering, nervous. · Incredulous, with a hint of panic.",
                    )

                    with gr.Accordion("💡 Instruction Examples", open=False):
                        gr.Markdown("""
**Emotion:** `Very happy.` · `Angry and frustrated.` · `Sad and defeated.` · `Excited and breathless.`

**Delivery:** `Whispering, nervous.` · `Slow and deliberate.` · `Fast-paced, urgent.` · `Warm and reassuring.`

**Character:** `Incredulous, with a hint of panic creeping in.` · `Sarcastic but keeping it together.`

**Style:** `Professional broadcast tone.` · `Casual conversation.` · `Dramatic storytelling.`

**Complex:** `Speak with slow gravitas, as if delivering difficult news.`

Plain prose in English or Chinese — no tags, no brackets. Per-sentence variation: use Voice Clone tab with batch input.
                        """)

                    tts_btn = gr.Button("Generate Speech", variant="primary", size="lg")

                with gr.Column(scale=2):
                    tts_audio = gr.Audio(label="Generated Audio", type="numpy")
                    tts_file = gr.Textbox(label="Saved To", interactive=False)

            tts_btn.click(
                fn=generate_tts,
                inputs=[tts_text, tts_language, tts_speaker, tts_instruct],
                outputs=[tts_audio, tts_file],
            )

        # ============ Tab 2: Voice Clone ============
        with gr.Tab("Voice Clone"):
            gr.Markdown("### Clone Any Voice from Reference Audio")

            with gr.Row():
                with gr.Column(scale=1):
                    clone_ref_audio = gr.Audio(
                        label="Reference Audio (5-30 seconds)",
                        type="numpy",
                    )
                    clone_ref_text = gr.Textbox(
                        label="Reference Text",
                        lines=3,
                        placeholder="Exact text spoken in the reference audio...",
                        info="What is being said in the reference audio",
                    )
                    clone_xvector = gr.Checkbox(
                        label="Use x-vector only (no reference text needed)",
                        value=False,
                        info="Faster but may be less accurate",
                    )

                with gr.Column(scale=1):
                    clone_target_text = gr.Textbox(
                        label="Target Text",
                        lines=5,
                        placeholder="Text you want the cloned voice to speak...",
                    )
                    clone_language = gr.Dropdown(
                        label="Language",
                        choices=LANGUAGES,
                        value="Auto",
                    )

            clone_btn = gr.Button("Clone & Generate", variant="primary", size="lg")

            with gr.Row():
                clone_audio = gr.Audio(label="Cloned Voice Output", type="numpy")
                clone_file = gr.Textbox(label="Saved To", interactive=False)

            clone_btn.click(
                fn=generate_voice_clone,
                inputs=[clone_ref_audio, clone_ref_text, clone_target_text, clone_language, clone_xvector],
                outputs=[clone_audio, clone_file],
            )

        # ============ Tab 3: Voice Design ============
        with gr.Tab("Voice Design"):
            gr.Markdown("### Create Custom Voices from Descriptions")

            with gr.Row():
                with gr.Column(scale=2):
                    design_text = gr.Textbox(
                        label="Text to Synthesize",
                        lines=5,
                        placeholder="Enter text to convert to speech...",
                        value="It's in the top drawer... wait, it's empty? No way, that's impossible!",
                    )

                    design_language = gr.Dropdown(
                        label="Language",
                        choices=LANGUAGES,
                        value="Auto",
                    )

                    design_instruct = gr.Textbox(
                        label="Voice Description",
                        lines=4,
                        placeholder="Describe the voice characteristics...",
                        value="Female, mid-20s, speaking with incredulous surprise and a hint of panic.",
                        info="Describe age, gender, tone, emotion, accent, speaking style, etc.",
                    )

                    design_btn = gr.Button("Design & Generate", variant="primary", size="lg")

                with gr.Column(scale=2):
                    design_audio = gr.Audio(label="Designed Voice Output", type="numpy")
                    design_file = gr.Textbox(label="Saved To", interactive=False)

                    gr.Markdown(
                        """
                        ### Voice Description Examples

                        **Character + emotion:**
                        - `"Male, 40s, deep authoritative voice, calm and reassuring"`
                        - `"Young woman, enthusiastic, speaking quickly with excitement"`
                        - `"Elderly gentleman, warm and wise, slight British accent"`
                        - `"Teenager, nervous and hesitant, mumbling slightly"`
                        - `"News anchor, professional, clear enunciation"`

                        **Acoustic detail:**
                        - `"Male, 17 years old, tenor range, gaining confidence — deeper breath support, vowels tighten when nervous"`
                        - `"Warm female voice, mid-30s, slightly husky, measured pace"`
                        - `"High pitch with noticeable variation, playful and deliberately cute"`

                        **Emotion state:**
                        - `"Speak with an incredulous tone, but with a hint of panic beginning to creep in"`
                        - `"Slow gravitas, as if delivering difficult news to someone you care about"`

                        Describe age, gender, timbre, emotion, accent, and speaking style in plain prose.
                        """
                    )

            design_btn.click(
                fn=generate_voice_design,
                inputs=[design_text, design_language, design_instruct],
                outputs=[design_audio, design_file],
            )

    gr.Markdown(
        """
        ---
        **Models:** [Qwen3-TTS-12Hz-1.7B](https://huggingface.co/collections/Qwen/qwen3-tts) |
        **License:** Apache 2.0 |
        **Paper:** [arXiv:2601.15621](https://arxiv.org/abs/2601.15621)

        *Only one model is loaded at a time to fit in 16GB VRAM. Switching tabs may reload models.*
        """
    )


if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=8009,
        share=False,
        favicon_path="/srv/containers/edq/media/favicons/qwen-tts.svg",
        allowed_paths=[OUTPUT_DIR],
        theme=gr.themes.Soft(primary_hue="indigo"),
    )
