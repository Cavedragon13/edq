#!/usr/bin/env python3
"""
YuE2 — full-song music generation with editable ABC scores.
Gradio front-end for the official `yue2` inference package (m-a-p/YuE2-3B).

Outputs land in ~/ai_generated/yue2/ as timestamped FLAC + MP3 plus a
per-song artifact folder (audio.flac, score.abc, plan.json, latents).
Dragonsuite port 8064.
"""

import gpu_runtime  # noqa: F401  — must precede torch (CUDA allocator config)

import os
import shutil
import subprocess
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import gradio as gr
import torch
from yue2 import YuE2Pipeline

MODEL_ID = "m-a-p/YuE2-3B"
VAE_ID = "m-a-p/YuE2-Vae"
PORT = 8064
OUTPUT_DIR = Path(os.path.expanduser("~/ai_generated/yue2"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
FAVICON = "/srv/containers/edq/media/favicons/yue2.svg"

print("YuE2")
print("====")
print(f"Loading {MODEL_ID} + {VAE_ID} on {'cuda' if torch.cuda.is_available() else 'cpu'} ...")
pipe = YuE2Pipeline.from_pretrained(
    MODEL_ID,
    device="cuda",
    vae=VAE_ID,
    progress=True,
)
print(f"Loaded. Output directory: {OUTPUT_DIR}")


# --------------------------------------------------------------------------- #
# Generation
# --------------------------------------------------------------------------- #
def _validate(style: str, lyrics: str):
    style = (style or "").strip()
    lyrics = (lyrics or "").strip()
    if not style:
        raise gr.Error("Describe the musical style first.")
    if not lyrics:
        raise gr.Error("Enter lyrics with section labels such as [Verse] and [Chorus].")
    if len(style) > 1_000:
        raise gr.Error("Keep the style prompt under 1,000 characters.")
    if len(lyrics) > 12_000:
        raise gr.Error("Keep the lyrics under 12,000 characters.")
    return style, lyrics


def _save(song, kind: str):
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"yue2_{kind}_{stamp}"
    run_dir = OUTPUT_DIR / base
    song.save_artifacts(str(run_dir))          # audio.flac, score.abc, plan.json, latents, settings
    flac_path = OUTPUT_DIR / f"{base}.flac"
    song.save(str(flac_path))
    mp3_path = OUTPUT_DIR / f"{base}.mp3"
    playable = flac_path
    if shutil.which("ffmpeg"):
        try:
            subprocess.run(
                ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(flac_path),
                 "-codec:a", "libmp3lame", "-b:a", "192k", str(mp3_path)],
                check=True, capture_output=True, text=True,
            )
            playable = mp3_path
        except (OSError, subprocess.CalledProcessError) as exc:
            print(f"  WARNING: MP3 encode failed, serving FLAC: {exc}")
    shutil.copy2(flac_path, OUTPUT_DIR / "latest.flac")
    if playable.suffix == ".mp3":
        shutil.copy2(playable, OUTPUT_DIR / "latest.mp3")
    score = song.abc or "No symbolic score was produced (direct-generation mode)."
    print(f"  saved {flac_path.name}  (artifacts in {run_dir.name}/)")
    return str(playable), str(flac_path), score, f"Saved to {flac_path}"


def _run(style, lyrics, abc, cot, steps, seed, cfg_scale, kind):
    style, lyrics = _validate(style, lyrics)
    abc = (abc or "").strip() or None
    if abc and cot == "off":
        raise gr.Error("A supplied ABC score needs 'Melody + chords' or 'Melody only' planning.")
    kwargs = dict(style=style, lyrics=lyrics, cot=cot, seed=int(seed))
    if abc:
        kwargs["abc"] = abc
    if cfg_scale and float(cfg_scale) > 1.0:
        kwargs["cfg_scale"] = float(cfg_scale)

    original = pipe.generation_config
    pipe.generation_config = replace(original, ode_steps=int(steps))
    try:
        with gpu_runtime.oom_guard("YuE2 song generation"):
            song = pipe(**kwargs)
    except RuntimeError as exc:
        raise gr.Error(str(exc))
    except Exception as exc:  # model-side validation errors surface cleanly
        raise gr.Error(f"Generation failed: {exc}")
    finally:
        pipe.generation_config = original
    return _save(song, kind)


def generate_song(style, lyrics, cot, steps, seed, cfg_scale):
    return _run(style, lyrics, None, cot, steps, seed, cfg_scale, "song")


def generate_from_score(style, lyrics, abc, cot, steps, seed, cfg_scale):
    if not (abc or "").strip():
        raise gr.Error("Paste an ABC score (melody-only for covers, or an edited score.abc).")
    return _run(style, lyrics, abc, cot, steps, seed, cfg_scale, "cover")


# --------------------------------------------------------------------------- #
# UI
# --------------------------------------------------------------------------- #
EXAMPLES = [
    [
        "Dreamy synth-pop, warm female lead vocal, pulsing bass, shimmering synths, uplifting",
        "[Verse]\nCity windows turn to gold\nEvery streetlight has a story\nWe are brave and we are bold\n"
        "Running toward the morning glory\n\n[Chorus]\nStay awake, the night is ours\nWe can dance beneath the stars\n"
        "Hold this moment, hold it tight\nWe are sparks inside the night\n\n[Outro]\nInside the night",
        "full", 16, 42, 1.0,
    ],
    [
        "Acoustic indie folk, intimate male vocal, fingerpicked guitar, gentle strings",
        "[Verse]\nDust is dancing in the doorway\nSummer settles on the road\nI can hear the old trees whisper\n"
        "All the secrets that they know\n\n[Chorus]\nTake me home across the river\nWhere the evening moves so slow\n"
        "If the wind can find its way there\nThen I know that I can go",
        "melody", 16, 831001, 1.0,
    ],
]

# Dark by default with localStorage persistence (house rule); toggle flips it.
DARK_JS = """
() => {
  const pref = localStorage.getItem('yue2-theme') || 'dark';
  document.body.classList.toggle('dark', pref === 'dark');
}
"""
TOGGLE_JS = """
() => {
  const dark = !document.body.classList.contains('dark');
  document.body.classList.toggle('dark', dark);
  localStorage.setItem('yue2-theme', dark ? 'dark' : 'light');
}
"""

with gr.Blocks(title="YuE2 — Music Generator", js=DARK_JS,
               theme=gr.themes.Soft(primary_hue="amber", secondary_hue="violet")) as demo:
    with gr.Row():
        gr.Markdown(
            "# 🎼 YuE2 — full-song generation with editable scores\n"
            "Lyrics + style prompt → complete 48 kHz stereo song (vocals + accompaniment). "
            "Edit the ABC score it writes and re-render. Outputs: `~/ai_generated/yue2/`"
        )
        theme_btn = gr.Button("🌙 / ☀️", scale=0, min_width=80)
    theme_btn.click(fn=None, js=TOGGLE_JS)

    with gr.Tabs():
        with gr.Tab("Create"):
            with gr.Row():
                with gr.Column(scale=3):
                    style = gr.Textbox(
                        label="Style", value=EXAMPLES[0][0],
                        placeholder="Genre, mood, vocal character, instruments, language, tempo…",
                    )
                    lyrics = gr.Textbox(
                        label="Lyrics (with [Verse] / [Chorus] / [Bridge] / [Outro] labels)",
                        lines=14, value=EXAMPLES[0][1],
                    )
                    with gr.Row():
                        cot = gr.Radio(
                            choices=[("Melody + chords", "full"), ("Melody only", "melody"), ("No score", "off")],
                            value="full", label="Symbolic planning",
                        )
                        steps = gr.Radio(
                            choices=[("Fast · 16 steps", 16), ("Best · 32 steps", 32)],
                            value=16, label="Render quality",
                        )
                    with gr.Row():
                        seed = gr.Number(value=42, precision=0, label="Seed")
                        cfg_scale = gr.Slider(1.0, 1.5, value=1.0, step=0.05,
                                              label="Text guidance (1.0 = model default)")
                    go = gr.Button("Generate song", variant="primary")
                with gr.Column(scale=2):
                    audio = gr.Audio(label="Generated song", type="filepath")
                    flac_dl = gr.File(label="Lossless FLAC")
                    score = gr.Textbox(label="Generated ABC score (copy into the Score tab to edit)",
                                       lines=10)
                    status = gr.Markdown()
            gr.Examples(examples=EXAMPLES, inputs=[style, lyrics, cot, steps, seed, cfg_scale],
                        cache_examples=False)
            go.click(generate_song, [style, lyrics, cot, steps, seed, cfg_scale],
                     [audio, flac_dl, score, status])

        with gr.Tab("From score (cover / edit)"):
            gr.Markdown(
                "Render a supplied ABC score: a melody-only transcription of an existing song "
                "(use **Melody only**), or an edited `score.abc` from a previous run "
                "(**Melody + chords**). Transcribe recordings with SheetSage2 separately — "
                "it is not bundled here."
            )
            with gr.Row():
                with gr.Column(scale=3):
                    c_style = gr.Textbox(label="Target style",
                                         placeholder="Jazz-funk, warm lead vocal, Rhodes piano, tight drums…")
                    c_lyrics = gr.Textbox(label="Lyrics (sections matching the score)", lines=10)
                    c_abc = gr.Textbox(label="ABC score", lines=12,
                                       placeholder="X:1\nT:Melody\nM:4/4\nL:1/8\nK:C\n…")
                    with gr.Row():
                        c_cot = gr.Radio(choices=[("Melody only", "melody"), ("Melody + chords", "full")],
                                         value="melody", label="Planning")
                        c_steps = gr.Radio(choices=[("Fast · 16", 16), ("Best · 32", 32)], value=16,
                                           label="Render quality")
                    with gr.Row():
                        c_seed = gr.Number(value=831001, precision=0, label="Seed")
                        c_cfg = gr.Slider(1.0, 1.5, value=1.0, step=0.05, label="Text guidance")
                    c_go = gr.Button("Render from score", variant="primary")
                with gr.Column(scale=2):
                    c_audio = gr.Audio(label="Rendered song", type="filepath")
                    c_flac = gr.File(label="Lossless FLAC")
                    c_score = gr.Textbox(label="Score used", lines=10)
                    c_status = gr.Markdown()
            c_go.click(generate_from_score, [c_style, c_lyrics, c_abc, c_cot, c_steps, c_seed, c_cfg],
                       [c_audio, c_flac, c_score, c_status])


if __name__ == "__main__":
    demo.queue(max_size=4, default_concurrency_limit=1)
    demo.launch(
        server_name="0.0.0.0",
        server_port=PORT,
        share=False,
        show_error=True,
        favicon_path=FAVICON if Path(FAVICON).exists() else None,
        allowed_paths=[str(OUTPUT_DIR)],
    )
