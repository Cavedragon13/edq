#!/bin/bash
# HeartMuLa Music Generator - Open Source Music Foundation Model
# Generates music from lyrics and style tags
# Port 8004, LAN accessible

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
HEARTMULA_DIR="$PROJECT_DIR/projects/heartmula"
VENV_DIR="$PROJECT_DIR/venv_heartmula"
MODEL_DIR="$HEARTMULA_DIR/ckpt"
OUTPUT_DIR="$HOME/ai_generated/heartmula"

echo "🎵 HeartMuLa Music Generator"
echo "============================"
echo "HeartMuLa-oss-3B - Open Source Music Foundation Model"
echo ""

# Check for CUDA
if command -v nvidia-smi &> /dev/null; then
    echo "🎮 GPU Info:"
    nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader 2>/dev/null || echo "  (nvidia-smi unavailable)"
    echo ""
fi

# Clone heartlib if not present
if [ ! -d "$HEARTMULA_DIR" ]; then
    echo "📥 Cloning HeartMuLa repository..."
    git clone https://github.com/HeartMuLa/heartlib.git "$HEARTMULA_DIR"
    echo "✓ Repository cloned"
    echo ""
fi

# Check/create venv with Python 3.10 (recommended for HeartMuLa)
if [ ! -d "$VENV_DIR" ]; then
    echo "📦 Creating virtual environment..."
    if command -v python3.10 &> /dev/null; then
        python3.10 -m venv "$VENV_DIR"
    else
        echo "⚠️  Python 3.10 not found, using python3..."
        python3 -m venv "$VENV_DIR"
    fi
fi

# Activate venv
source "$VENV_DIR/bin/activate"

# Check if heartlib is installed
if ! python -c "import heartlib" 2>/dev/null; then
    echo "📦 Installing HeartMuLa dependencies..."
    echo "   ⏳ First run downloads ~2GB of packages - please wait..."
    echo ""
    pip install --upgrade pip
    # Install heartlib with all dependencies (includes torch 2.4.1)
    cd "$HEARTMULA_DIR"
    pip install -e .
    # Install gradio and HF CLI separately
    pip install "gradio>=4.0.0" "huggingface_hub[cli]"
    echo ""
    echo "✓ Installation complete"
    echo ""
fi

# Check/download model weights
if [ ! -d "$MODEL_DIR/HeartMuLa-oss-3B" ]; then
    echo "📥 Downloading HeartMuLa model weights..."
    echo "   This will download ~10GB of model files..."
    mkdir -p "$MODEL_DIR"

    # Download HeartMuLaGen (tokenizer and config)
    echo "   Downloading HeartMuLaGen files..."
    huggingface-cli download HeartMuLa/HeartMuLaGen tokenizer.json gen_config.json --local-dir "$MODEL_DIR"

    # Download HeartMuLa-oss-3B
    echo "   Downloading HeartMuLa-oss-3B (~6GB)..."
    huggingface-cli download HeartMuLa/HeartMuLa-oss-3B --local-dir "$MODEL_DIR/HeartMuLa-oss-3B"

    # Download HeartCodec-oss
    echo "   Downloading HeartCodec-oss (~2GB)..."
    huggingface-cli download HeartMuLa/HeartCodec-oss --local-dir "$MODEL_DIR/HeartCodec-oss"

    echo "✓ Models downloaded to $MODEL_DIR"
    echo ""
fi

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Create local app.py if not exists
APP_FILE="$HEARTMULA_DIR/app_local.py"
if [ ! -f "$APP_FILE" ]; then
    echo "📝 Creating local Gradio app..."
    cat > "$APP_FILE" << 'PYEOF'
#!/usr/bin/env python3
"""HeartMuLa Music Generator - Local Gradio Interface"""

import os
import tempfile
import datetime
import torch
import gradio as gr
from heartlib import HeartMuLaGenPipeline

# Configuration
MODEL_DIR = os.environ.get("HEARTMULA_MODEL_DIR", "./ckpt")
OUTPUT_DIR = os.path.expanduser("~/ai_generated/heartmula")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Determine device and dtype
if torch.cuda.is_available():
    device = torch.device("cuda")
    dtype = torch.bfloat16
    print(f"Using CUDA with bfloat16")
else:
    device = torch.device("cpu")
    dtype = torch.float32
    print(f"Using CPU with float32 (this will be slow)")

print(f"Loading HeartMuLa pipeline from {MODEL_DIR}...")
pipe = HeartMuLaGenPipeline.from_pretrained(
    MODEL_DIR,
    device=device,
    dtype=dtype,
    version="3B",
)
print("Pipeline loaded successfully!")


def generate_music(
    lyrics: str,
    tags: str,
    max_duration_seconds: int,
    temperature: float,
    topk: int,
    cfg_scale: float,
    progress=gr.Progress(track_tqdm=True),
):
    """Generate music from lyrics and tags."""
    if not lyrics.strip():
        raise gr.Error("Please enter some lyrics!")

    if not tags.strip():
        raise gr.Error("Please enter at least one tag!")

    # Create output file with timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(OUTPUT_DIR, f"heartmula_{timestamp}.mp3")

    max_audio_length_ms = max_duration_seconds * 1000

    with torch.no_grad():
        pipe(
            {
                "lyrics": lyrics,
                "tags": tags,
            },
            max_audio_length_ms=max_audio_length_ms,
            save_path=output_path,
            topk=topk,
            temperature=temperature,
            cfg_scale=cfg_scale,
        )

    return output_path


# Example lyrics
EXAMPLE_LYRICS = """[Intro]

[Verse]
The sun creeps in across the floor
I hear the traffic outside the door
Another morning comes to life
As shadows dance in morning light

[Chorus]
Just another day
Every single day
Moving through the haze
Finding my own way

[Verse]
Coffee steaming in my hands
Making simple plans
The world outside awaits
Beyond these garden gates

[Chorus]
Just another day
Every single day
Moving through the haze
Finding my own way

[Outro]
Just another day
Every single day"""

EXAMPLE_TAGS = "piano,happy,uplifting,pop"

# Build the Gradio interface
with gr.Blocks(
    title="HeartMuLa Music Generator",
    theme=gr.themes.Soft(primary_hue="purple"),
) as demo:
    gr.Markdown(
        """
        # HeartMuLa Music Generator

        Generate music from lyrics and tags using [HeartMuLa](https://github.com/HeartMuLa/heartlib),
        an open-source music foundation model achieving Suno-level quality.

        **Instructions:**
        1. Enter your lyrics with structure tags like `[Verse]`, `[Chorus]`, `[Bridge]`, etc.
        2. Add comma-separated tags describing the music style (e.g., `piano,happy,romantic`)
        3. Adjust generation parameters as needed
        4. Click "Generate Music" and wait for your song!

        *Note: Generation takes about 1x real-time (2 min song = ~2 min generation)*
        """
    )

    with gr.Row():
        with gr.Column(scale=1):
            lyrics_input = gr.Textbox(
                label="Lyrics",
                placeholder="Enter lyrics with structure tags like [Verse], [Chorus], etc.",
                lines=20,
                value=EXAMPLE_LYRICS,
            )

            tags_input = gr.Textbox(
                label="Tags",
                placeholder="piano,happy,romantic,synthesizer",
                value=EXAMPLE_TAGS,
                info="Comma-separated tags describing the music style",
            )

            with gr.Accordion("Advanced Settings", open=False):
                max_duration = gr.Slider(
                    minimum=30,
                    maximum=240,
                    value=120,
                    step=10,
                    label="Max Duration (seconds)",
                    info="Maximum length of generated audio",
                )

                temperature = gr.Slider(
                    minimum=0.1,
                    maximum=2.0,
                    value=1.0,
                    step=0.1,
                    label="Temperature",
                    info="Higher = more creative, Lower = more consistent",
                )

                topk = gr.Slider(
                    minimum=1,
                    maximum=100,
                    value=50,
                    step=1,
                    label="Top-K",
                    info="Number of top tokens to sample from",
                )

                cfg_scale = gr.Slider(
                    minimum=1.0,
                    maximum=3.0,
                    value=1.5,
                    step=0.1,
                    label="CFG Scale",
                    info="Classifier-free guidance scale",
                )

            generate_btn = gr.Button("Generate Music", variant="primary", size="lg")

        with gr.Column(scale=1):
            audio_output = gr.Audio(
                label="Generated Music",
                type="filepath",
            )

            gr.Markdown(
                f"""
                ### Tips for Better Results
                - Use structured lyrics with section tags
                - Be specific with your style tags
                - Try different temperature values for variety
                - Shorter durations generate faster

                ### Example Tags
                - **Instruments:** piano, guitar, drums, synthesizer, violin, bass
                - **Mood:** happy, sad, romantic, energetic, calm, melancholic
                - **Genre:** pop, rock, jazz, classical, electronic, folk
                - **Tempo:** fast, slow, upbeat, relaxed

                ### Output Location
                Generated files saved to: `{OUTPUT_DIR}`
                """
            )

    generate_btn.click(
        fn=generate_music,
        inputs=[
            lyrics_input,
            tags_input,
            max_duration,
            temperature,
            topk,
            cfg_scale,
        ],
        outputs=audio_output,
    )

    gr.Markdown(
        """
        ---
        **Model:** [HeartMuLa-oss-3B](https://huggingface.co/HeartMuLa/HeartMuLa-oss-3B) |
        **Paper:** [arXiv](https://arxiv.org/abs/2601.10547) |
        **Code:** [GitHub](https://github.com/HeartMuLa/heartlib)

        *Licensed under Apache 2.0*
        """
    )

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=8004,
        share=False,
    )
PYEOF
    echo "✓ Local app created"
    echo ""
fi

echo "🌐 Starting HeartMuLa WebUI..."
echo "📡 Local:   http://localhost:8004"
echo "📡 LAN:     http://192.168.7.226:8004"
echo ""
echo "Features:"
echo "  - Lyrics-to-music generation"
echo "  - Style control via tags"
echo "  - Section structure support ([Verse], [Chorus], etc.)"
echo "  - Suno-level quality (open source!)"
echo ""
echo "Output saves to: $OUTPUT_DIR"
echo ""
echo "Press Ctrl+C to stop"
echo ""

cd "$HEARTMULA_DIR"
export HEARTMULA_MODEL_DIR="$MODEL_DIR"
export GRADIO_SERVER_NAME="0.0.0.0"
export GRADIO_SERVER_PORT="8004"

# Memory optimization for 16GB VRAM
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

python app_local.py
