#!/usr/bin/env python3
"""Gradio wrapper for Agentic Video Editor.

The upstream project is CLI-first. This wrapper keeps the Dragonsuite
dashboard entry simple while preserving the CLI contract and persistent
output rules.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

import gradio as gr


PROJECT_DIR = Path("/srv/containers/edq/projects/agentic-video-editor")
OUTPUT_BASE = Path.home() / "ai_generated" / "agentic_video"
DEFAULT_PIPELINE = PROJECT_DIR / "pipelines" / "ugc-ad.yaml"
DEFAULT_STYLE = PROJECT_DIR / "styles" / "dtc-testimonial.yaml"
OUTPUT_BASE.mkdir(parents=True, exist_ok=True)


def _brief_from_text(creative_brief: str) -> dict[str, object]:
    text = creative_brief.strip()
    return {
        "product": text[:120] or "Uploaded video",
        "audience": "general audience",
        "tone": text,
        "duration_seconds": 15,
    }


def _find_output_video(stdout: str, run_dir: Path) -> Path | None:
    match = re.search(r"output video\s*:\s*(.+)", stdout)
    if match:
        raw = match.group(1).strip()
        if raw and raw.lower() != "none":
            path = Path(raw)
            if not path.is_absolute():
                path = PROJECT_DIR / path
            if path.exists() and path.suffix.lower() == ".mp4":
                return path

    candidates: list[Path] = []
    for root in (run_dir, PROJECT_DIR / "output"):
        if root.exists():
            candidates.extend(root.rglob("*.mp4"))
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _persist_video(video_path: Path, run_dir: Path) -> Path:
    destination = run_dir / video_path.name
    if video_path.resolve() != destination.resolve():
        shutil.copy2(video_path, destination)
    return destination


def process_video(video_file, creative_brief, pipeline_yaml=""):
    if not video_file:
        return None, "Please upload a video file."

    if not creative_brief or not creative_brief.strip():
        return None, "Please provide a creative brief."

    footage_dir = Path(tempfile.mkdtemp(prefix="agentic_video_"))
    try:
        uploaded = Path(video_file)
        shutil.copy2(uploaded, footage_dir / uploaded.name)

        run_dir = OUTPUT_BASE / datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir.mkdir(parents=True, exist_ok=True)

        pipeline_path = DEFAULT_PIPELINE
        if pipeline_yaml and pipeline_yaml.strip():
            pipeline_path = run_dir / "pipeline.yaml"
            pipeline_path.write_text(pipeline_yaml, encoding="utf-8")

        brief_path = run_dir / "brief.json"
        brief_path.write_text(
            json.dumps(_brief_from_text(creative_brief), indent=2),
            encoding="utf-8",
        )

        cmd = [
            "ave",
            "edit",
            "--footage-dir",
            str(footage_dir),
            "--brief",
            str(brief_path),
            "--pipeline",
            str(pipeline_path),
            "--style",
            str(DEFAULT_STYLE),
            "--output-dir",
            str(run_dir),
            "--no-approval",
        ]

        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_DIR),
            capture_output=True,
            text=True,
            timeout=3600,
        )

        log_path = run_dir / "ave_run.log"
        log_path.write_text(
            "$ " + " ".join(cmd) + "\n\n"
            + "STDOUT\n"
            + result.stdout
            + "\n\nSTDERR\n"
            + result.stderr,
            encoding="utf-8",
        )

        if result.returncode != 0:
            stderr_tail = result.stderr[-4000:] if result.stderr else ""
            return None, f"Pipeline failed. Log: {log_path}\n\n{stderr_tail}"

        output_video = _find_output_video(result.stdout, run_dir)
        if output_video is None:
            return None, f"No output video found. Log: {log_path}"

        persistent_video = _persist_video(output_video, run_dir)
        return str(persistent_video), f"Video processed successfully.\nOutput: {persistent_video}"

    except subprocess.TimeoutExpired:
        return None, "Processing timeout after 1 hour."
    except Exception as exc:
        return None, f"Error: {exc}"


with gr.Blocks(title="Agentic Video Editor", theme=gr.themes.Soft()) as iface:
    gr.Markdown("# Agentic Video Editor")

    with gr.Row():
        with gr.Column():
            video_input = gr.File(label="Footage", file_types=["video"])
            brief_input = gr.Textbox(
                label="Creative Brief",
                placeholder="Create a 15-second upbeat cut from this footage.",
                lines=3,
            )
            pipeline_input = gr.Textbox(
                label="Pipeline YAML Override",
                placeholder="Leave empty for the default UGC ad pipeline.",
                lines=2,
            )
            submit_btn = gr.Button("Process Video", variant="primary")

        with gr.Column():
            video_output = gr.Video(label="Output Video")
            status_output = gr.Textbox(label="Status", interactive=False)

    submit_btn.click(
        process_video,
        inputs=[video_input, brief_input, pipeline_input],
        outputs=[video_output, status_output],
    )

    gr.Markdown(f"Output folder: `{OUTPUT_BASE}`")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8044"))
    iface.launch(
        server_name="0.0.0.0",
        server_port=port,
        share=False,
        allowed_paths=[str(OUTPUT_BASE)],
    )
