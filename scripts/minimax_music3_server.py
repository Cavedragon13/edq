#!/usr/bin/env python3
"""
MiniMax Music 3 — full-song text-to-music generation.

HF repo: MiniMaxAI/MiniMax-Music3 (8B Qwen3-based global LLM + 0.6B depth
decoder -> fused hidden states condition a 2.4B flow-matching transformer ->
Flow-VAE decoder -> 44.1kHz stereo audio). Loaded via diffusers' ModularPipeline
with the language model group-offloaded to CPU so peak VRAM stays ~8GB on a
single GPU, instead of the ~23GB a resident bf16 load would need.

Port: 8059
"""

import gpu_runtime  # noqa: E402  (must import before torch — configures CUDA allocator)

import gc
import os
from datetime import datetime
from pathlib import Path

import gradio as gr
import soundfile as sf
import torch

MODELS_DIR = Path("/srv/containers/edq/models/minimax-music3")
OUTPUT_DIR = Path(os.path.expanduser("~/ai_generated/minimax-music3"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SECTION_TAGS = "[intro] [verse] [pre-chorus] [chorus] [bridge] [instrumental] [solo] [outro]"

pipe = None
load_error = None


def clear_memory():
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def check_model():
    if not (MODELS_DIR / "modular_model_index.json").exists():
        return (
            "MiniMax Music 3 model files not found.\n"
            "Run: bash scripts/download_minimax_music3_models.sh"
        )
    return None


def load_pipeline():
    global pipe, load_error
    if pipe is not None:
        return True, "Model loaded"
    if load_error:
        return False, load_error

    issue = check_model()
    if issue:
        load_error = issue
        return False, issue

    try:
        from diffusers import ComponentsManager, ModularPipeline
        from diffusers.hooks.group_offloading import apply_group_offloading

        print("Loading MiniMax Music 3 (group-offloaded language model)...")
        manager = ComponentsManager()
        manager.enable_auto_cpu_offload(device="cuda")
        p = ModularPipeline.from_pretrained(str(MODELS_DIR), components_manager=manager)
        # modular_model_index.json hardcodes the original hub repo id per component, so
        # load_components() would otherwise call out to the Hub for each one. Override with
        # our local dir (applies to every component; per-component `subfolder` is untouched).
        p.load_components(
            dtype=torch.bfloat16,
            pretrained_model_name_or_path=str(MODELS_DIR),
            local_files_only=True,
        )

        apply_group_offloading(
            p.language_model,
            onload_device=torch.device("cuda"),
            offload_type="leaf_level",
            use_stream=True,
            low_cpu_mem_usage=True,
        )

        pipe = p
        print("MiniMax Music 3 loaded.")
        return True, "Model loaded"
    except Exception as exc:
        import traceback

        load_error = f"{exc}\n\n{traceback.format_exc()}"
        clear_memory()
        return False, load_error


def build_prompt(genre, bpm, key, vocal, arrangement, extra):
    parts = []
    meta = ", ".join(x for x in (genre, bpm, key) if x)
    if meta:
        parts.append(meta + ".")
    if vocal:
        parts.append(f"Vocals: {vocal}.")
    if arrangement:
        parts.append(f"Arrangement: {arrangement}.")
    if extra:
        parts.append(extra.strip())
    return " ".join(parts).strip()


def generate_music(
    lyrics, genre, bpm, key, vocal, arrangement, extra_desc,
    duration, seed, guidance_scale, progress=gr.Progress(),
):
    if not lyrics or not lyrics.strip():
        return None, "Enter lyrics with section tags (each tag on its own line)."

    prompt = build_prompt(genre, bpm, key, vocal, arrangement, extra_desc)
    if not prompt:
        return None, "Enter at least a genre or music description."

    progress(0.05, desc="Loading model...")
    ok, message = load_pipeline()
    if not ok:
        return None, f"Failed to load model:\n{message}"

    try:
        progress(0.15, desc="Generating (autoregressive stage dominates runtime)...")
        with gpu_runtime.oom_guard("music generation"):
            from diffusers import ClassifierFreeGuidance

            pipe.update_components(guider=ClassifierFreeGuidance(guidance_scale=float(guidance_scale)))
            result = pipe(
                prompt=prompt,
                lyrics=lyrics.strip(),
                audio_duration=float(duration),
                generator=torch.Generator("cuda").manual_seed(int(seed)),
                output="audios",
            )
        audio = result[0]

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = OUTPUT_DIR / f"minimax_music3_{timestamp}.wav"
        sf.write(str(output_path), audio.T, pipe.sampling_rate)
        clear_memory()
        return str(output_path), f"Saved: {output_path}\nPrompt used: {prompt}"
    except RuntimeError as exc:
        clear_memory()
        return None, f"Error:\n{exc}"
    except Exception as exc:
        import traceback

        clear_memory()
        return None, f"Error:\n{exc}\n\n{traceback.format_exc()}"


with gr.Blocks(title="MiniMax Music 3", theme=gr.themes.Soft(primary_hue="rose")) as demo:
    gr.Markdown("# MiniMax Music 3 — Full-Song Generation")
    gr.Markdown(
        "Generates complete songs up to 5 minutes from lyrics + a music description. "
        f"Section tags ({SECTION_TAGS}) must each be on their own line — text sharing "
        "a line with a tag is dropped."
    )

    with gr.Row():
        with gr.Column():
            lyrics_in = gr.Textbox(
                label="Lyrics (with section tags)",
                lines=10,
                placeholder="[verse]\nMorning light filtering through the pine\n"
                "Every quiet street is yours and mine\n[chorus]\n"
                "Softly the world begins to breathe",
            )
            with gr.Row():
                genre_in = gr.Textbox(label="Genre / subgenre", placeholder="Genre: acoustic pop", scale=2)
                bpm_in = gr.Textbox(label="BPM", placeholder="BPM: 96", scale=1)
                key_in = gr.Textbox(label="Key", placeholder="Key: C major", scale=1)
            vocal_in = gr.Textbox(
                label="Vocal details",
                placeholder="soft female lead, close and breathy, light stacked harmonies in the chorus",
                lines=2,
            )
            arrangement_in = gr.Textbox(
                label="Arrangement",
                placeholder="fingerpicked guitar and soft piano; brushed drums and upright bass enter in the chorus",
                lines=2,
            )
            extra_in = gr.Textbox(label="Additional description (optional, free text)", lines=2)
            with gr.Row():
                duration_in = gr.Slider(label="Duration (s)", minimum=10, maximum=300, value=60, step=5)
                seed_in = gr.Number(label="Seed", value=7, precision=0)
                guidance_in = gr.Slider(label="Guidance scale", minimum=0.5, maximum=5.0, value=1.7, step=0.1)
            generate_btn = gr.Button("Generate", variant="primary")
        with gr.Column():
            audio_out = gr.Audio(label="Output", type="filepath")
            status_out = gr.Textbox(label="Status", lines=6)

    generate_btn.click(
        fn=generate_music,
        inputs=[
            lyrics_in, genre_in, bpm_in, key_in, vocal_in, arrangement_in, extra_in,
            duration_in, seed_in, guidance_in,
        ],
        outputs=[audio_out, status_out],
        show_progress=True,
    )


if __name__ == "__main__":
    print("MiniMax Music 3")
    print(f"Models: {MODELS_DIR}")
    print(f"Output: {OUTPUT_DIR}")
    issue = check_model()
    if issue:
        print(issue)
    demo.launch(
        server_name="0.0.0.0",
        server_port=8059,
        share=False,
        allowed_paths=[str(OUTPUT_DIR)],
        show_error=True,
    )
