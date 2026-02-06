#!/usr/bin/env python3
"""
Wan2.2-Animate-14B Gradio Interface
Optimized for RTX 5070 Ti (16GB VRAM)
"""

import gradio as gr
import torch
import os
import subprocess
import tempfile
from pathlib import Path
import shutil

# Configuration
MODEL_DIR = os.path.expanduser("~/wan-animate/models/Wan2.2-Animate-14B")
REPO_DIR = os.path.expanduser("~/wan-animate/Wan2.2")
TEMP_DIR = tempfile.mkdtemp(prefix="wan_animate_")

def check_setup():
    """Check if model and repository are properly set up"""
    if not os.path.exists(MODEL_DIR):
        return False, f"Model not found at {MODEL_DIR}. Please run setup script first."
    if not os.path.exists(REPO_DIR):
        return False, f"Repository not found at {REPO_DIR}. Please run setup script first."
    return True, "Setup verified"

def preprocess_video(video_path, image_path, mode="animate", resolution_width=1280, resolution_height=720):
    """
    Preprocess video and character image

    Args:
        video_path: Path to input video
        image_path: Path to character image
        mode: 'animate' or 'replace'
        resolution_width: Output width
        resolution_height: Output height
    """
    # Create unique output directory
    output_dir = os.path.join(TEMP_DIR, f"{mode}_{os.path.basename(video_path).split('.')[0]}")
    os.makedirs(output_dir, exist_ok=True)

    # Build preprocessing command
    cmd = [
        "python", f"{REPO_DIR}/wan/modules/animate/preprocess/preprocess_data.py",
        "--ckpt_path", f"{MODEL_DIR}/process_checkpoint",
        "--video_path", video_path,
        "--refer_path", image_path,
        "--save_path", output_dir,
        "--resolution_area", str(resolution_width), str(resolution_height),
    ]

    if mode == "animate":
        cmd.extend(["--retarget_flag", "--use_flux"])
    else:  # replace mode
        cmd.extend([
            "--iterations", "3",
            "--k", "7",
            "--w_len", "1",
            "--h_len", "1",
            "--replace_flag"
        ])

    try:
        result = subprocess.run(
            cmd,
            cwd=REPO_DIR,
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode != 0:
            return None, f"Preprocessing failed:\n{result.stderr}"

        return output_dir, "Preprocessing completed successfully"

    except subprocess.TimeoutExpired:
        return None, "Preprocessing timed out (5 minutes)"
    except Exception as e:
        return None, f"Error during preprocessing: {str(e)}"

def generate_animation(preprocessed_dir, mode="animate", use_optimization=True):
    """
    Generate animated video using preprocessed data

    Args:
        preprocessed_dir: Directory with preprocessed data
        mode: 'animate' or 'replace'
        use_optimization: Enable memory optimizations
    """
    # Build generation command
    cmd = [
        "python", f"{REPO_DIR}/generate.py",
        "--task", "animate-14B",
        "--ckpt_dir", MODEL_DIR,
        "--src_root_path", preprocessed_dir,
        "--refert_num", "1",
    ]

    if mode == "replace":
        cmd.extend(["--replace_flag", "--use_relighting_lora"])

    # Set environment variables for optimization
    env = os.environ.copy()
    if use_optimization:
        # Enable memory optimizations
        env["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
        env["CUDA_VISIBLE_DEVICES"] = "0"

    try:
        result = subprocess.run(
            cmd,
            cwd=REPO_DIR,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minutes
            env=env
        )

        if result.returncode != 0:
            return None, f"Generation failed:\n{result.stderr}"

        # Find output video
        output_video = None
        for file in Path(preprocessed_dir).rglob("*.mp4"):
            if "output" in file.name or "result" in file.name:
                output_video = str(file)
                break

        if not output_video and list(Path(preprocessed_dir).rglob("*.mp4")):
            output_video = str(list(Path(preprocessed_dir).rglob("*.mp4"))[-1])

        if output_video:
            return output_video, "Generation completed successfully"
        else:
            return None, "Generation completed but no output video found"

    except subprocess.TimeoutExpired:
        return None, "Generation timed out (10 minutes). Your GPU may not have enough memory."
    except Exception as e:
        return None, f"Error during generation: {str(e)}"

def process_full_pipeline(video, character_image, mode, resolution_width, resolution_height, use_optimization):
    """
    Run full pipeline: preprocess + generate
    """
    # Preprocess
    yield None, "Step 1/2: Preprocessing video and character image...", gr.update(visible=True)

    preprocessed_dir, preprocess_msg = preprocess_video(
        video, character_image, mode, resolution_width, resolution_height
    )

    if preprocessed_dir is None:
        yield None, f"❌ {preprocess_msg}", gr.update(visible=True)
        return

    # Generate
    yield None, f"✓ {preprocess_msg}\nStep 2/2: Generating animation (this may take several minutes)...", gr.update(visible=True)

    output_video, generate_msg = generate_animation(preprocessed_dir, mode, use_optimization)

    if output_video:
        yield output_video, f"✓ {preprocess_msg}\n✓ {generate_msg}", gr.update(visible=False)
    else:
        yield None, f"✓ {preprocess_msg}\n❌ {generate_msg}", gr.update(visible=True)

# Create Gradio interface
with gr.Blocks(title="Wan2.2-Animate-14B") as app:
    gr.Markdown("""
    # 🎬 Wan2.2-Animate-14B Character Animation

    Transform characters in videos using AI animation and replacement.

    **⚠️ Hardware Note:** This is a 14B parameter model. With 16GB VRAM, processing may be slow or fail for long/high-resolution videos.
    For best results, use short videos (5-10 seconds) at moderate resolution.
    """)

    # Check setup
    setup_ok, setup_msg = check_setup()
    if not setup_ok:
        gr.Markdown(f"### ❌ Setup Error\n{setup_msg}")
    else:
        with gr.Row():
            with gr.Column(scale=1):
                mode = gr.Radio(
                    choices=["animate", "replace"],
                    value="animate",
                    label="Mode",
                    info="Animate: Character mimics video motion | Replace: Replace character in video"
                )

                video_input = gr.Video(
                    label="Input Video",
                    info="Upload video with motion/character to animate"
                )

                image_input = gr.Image(
                    label="Character Image",
                    type="filepath",
                    info="Upload character image to animate"
                )

                with gr.Accordion("Advanced Settings", open=False):
                    resolution_width = gr.Slider(
                        minimum=512, maximum=1920, value=1280, step=64,
                        label="Resolution Width"
                    )
                    resolution_height = gr.Slider(
                        minimum=512, maximum=1080, value=720, step=64,
                        label="Resolution Height"
                    )
                    use_optimization = gr.Checkbox(
                        value=True,
                        label="Enable Memory Optimizations",
                        info="Required for 16GB VRAM"
                    )

                generate_btn = gr.Button("🎬 Generate Animation", variant="primary", size="lg")

            with gr.Column(scale=1):
                output_video = gr.Video(label="Output Video")
                status_text = gr.Textbox(label="Status", lines=5, interactive=False)
                loading_indicator = gr.HTML(
                    """<div style='text-align: center; padding: 20px;'>
                    <div class='loader' style='border: 8px solid #f3f3f3; border-top: 8px solid #3498db;
                    border-radius: 50%; width: 60px; height: 60px; animation: spin 1s linear infinite; margin: 0 auto;'>
                    </div><style>@keyframes spin{0%{transform:rotate(0deg)}100%{transform:rotate(360deg)}}</style>
                    <p style='margin-top: 10px;'>Processing... This may take several minutes.</p></div>""",
                    visible=False
                )

    gr.Markdown("""
    ### 📝 Tips
    - **Short videos work best** (5-15 seconds)
    - **Lower resolution** if you encounter memory errors
    - **Animate mode**: Use video with clear human motion + any character image
    - **Replace mode**: Use video with a character + replacement character image
    - First run will be slower due to model loading

    ### 🔗 Resources
    - [Model Card](https://huggingface.co/Wan-AI/Wan2.2-Animate-14B)
    - [GitHub Repository](https://github.com/Wan-Video/Wan2.2)
    - [Official Website](https://wan.video/)
    """)

    # Connect generate button
    if setup_ok:
        generate_btn.click(
            fn=process_full_pipeline,
            inputs=[video_input, image_input, mode, resolution_width, resolution_height, use_optimization],
            outputs=[output_video, status_text, loading_indicator]
        )

if __name__ == "__main__":
    print("🚀 Starting Wan2.2-Animate-14B Gradio Interface...")
    print(f"📁 Model directory: {MODEL_DIR}")
    print(f"📁 Repository directory: {REPO_DIR}")
    print(f"📁 Temporary directory: {TEMP_DIR}")
    print()

    setup_ok, setup_msg = check_setup()
    if not setup_ok:
        print(f"❌ {setup_msg}")
        print("\n🔧 Please run the setup script first:")
        print("   bash ~/setup-wan-animate.sh")
    else:
        print(f"✓ {setup_msg}")

    print("\n🌐 Launching Gradio interface...")
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        inbrowser=True
    )
