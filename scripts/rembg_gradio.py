#!/usr/bin/env python3
"""
Rembg Background Remover - Gradio Interface
Dragonsuite service for removing image backgrounds with AI
Port: 8012
"""

import gradio as gr
from rembg import remove, new_session
from PIL import Image
import os
from pathlib import Path
from datetime import datetime

# Output directory
OUTPUT_DIR = Path.home() / "ai_generated" / "rembg"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Available models
MODELS = {
    "u2net (General - Best Quality)": "u2net",
    "u2net_human_seg (People/Portraits)": "u2net_human_seg",
    "isnet-general-use (Fast & Good)": "isnet-general-use",
    "isnet-anime (Anime/Illustrations)": "isnet-anime",
    "silueta (Lightweight)": "silueta",
    "u2netp (Fast, Lower Quality)": "u2netp",
}

# Session cache
_sessions = {}

def get_session(model_name: str):
    """Get or create a session for the given model."""
    if model_name not in _sessions:
        print(f"Loading model: {model_name}")
        _sessions[model_name] = new_session(model_name)
    return _sessions[model_name]

def remove_background(
    input_image: Image.Image,
    model_choice: str,
    alpha_matting: bool,
    alpha_matting_foreground_threshold: int,
    alpha_matting_background_threshold: int,
    post_process_mask: bool,
) -> tuple[Image.Image, str]:
    """Remove background from image."""
    if input_image is None:
        return None, "Please upload an image"

    model_name = MODELS[model_choice]
    session = get_session(model_name)

    # Remove background
    output = remove(
        input_image,
        session=session,
        alpha_matting=alpha_matting,
        alpha_matting_foreground_threshold=alpha_matting_foreground_threshold,
        alpha_matting_background_threshold=alpha_matting_background_threshold,
        post_process_mask=post_process_mask,
    )

    # Save output
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = OUTPUT_DIR / f"rembg_{timestamp}.png"
    output.save(output_path, "PNG")

    return output, f"Saved to: {output_path}"

def create_ui():
    """Create the Gradio interface."""
    with gr.Blocks(
        title="Rembg - Background Remover",
        theme=gr.themes.Soft(primary_hue="green"),
    ) as app:
        gr.Markdown("""
        # 🐉 Rembg - AI Background Remover
        Remove backgrounds from images with one click. Outputs PNG with transparency.
        """)

        with gr.Row():
            with gr.Column():
                input_image = gr.Image(
                    label="Input Image",
                    type="pil",
                    sources=["upload", "clipboard"],
                )

                model_choice = gr.Dropdown(
                    choices=list(MODELS.keys()),
                    value="isnet-general-use (Fast & Good)",
                    label="Model",
                    info="Different models work better for different subjects",
                )

                with gr.Accordion("Advanced Options", open=False):
                    alpha_matting = gr.Checkbox(
                        label="Alpha Matting",
                        value=False,
                        info="Better edges but slower. Good for hair/fur.",
                    )
                    fg_threshold = gr.Slider(
                        minimum=0,
                        maximum=255,
                        value=240,
                        step=1,
                        label="Foreground Threshold",
                        visible=True,
                    )
                    bg_threshold = gr.Slider(
                        minimum=0,
                        maximum=255,
                        value=10,
                        step=1,
                        label="Background Threshold",
                        visible=True,
                    )
                    post_process = gr.Checkbox(
                        label="Post-process Mask",
                        value=False,
                        info="Clean up mask edges",
                    )

                submit_btn = gr.Button("Remove Background", variant="primary", size="lg")

            with gr.Column():
                output_image = gr.Image(
                    label="Result (Transparent PNG)",
                    type="pil",
                )
                status = gr.Textbox(label="Status", interactive=False)

        # Examples
        gr.Markdown("### Model Guide")
        gr.Markdown("""
        | Model | Best For | Speed |
        |-------|----------|-------|
        | **isnet-general-use** | General purpose, good balance | Fast |
        | **u2net** | Best quality, fine details | Slower |
        | **u2net_human_seg** | People, portraits | Medium |
        | **isnet-anime** | Anime, illustrations, cartoons | Fast |
        | **silueta** | Simple subjects, quick tests | Fastest |
        """)

        submit_btn.click(
            fn=remove_background,
            inputs=[
                input_image,
                model_choice,
                alpha_matting,
                fg_threshold,
                bg_threshold,
                post_process,
            ],
            outputs=[output_image, status],
        )

    return app

if __name__ == "__main__":
    print("=" * 50)
    print("Rembg Background Remover")
    print(f"Output directory: {OUTPUT_DIR}")
    print("=" * 50)

    app = create_ui()
    app.launch(
        server_name="0.0.0.0",
        server_port=8012,
        share=False,
        show_error=True,
    )
