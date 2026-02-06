#!/usr/bin/env python3
"""Generate TTS audio for vocab word using Qwen3-TTS"""

import sys
import os
import torch
import soundfile as sf
from pathlib import Path

# Add qwen_tts to path if needed
sys.path.insert(0, '/srv/containers/edq/venv_qwen3_tts/lib/python3.12/site-packages')

from qwen_tts import Qwen3TTSModel, Qwen3TTSTokenizer

# Configuration
OUTPUT_DIR = Path("/srv/containers/edq/projects/remotion-vocab/public/audio")
SPEAKER = "Eric"  # Male voice for "detention" vibe
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE = torch.bfloat16 if DEVICE == "cuda" else torch.float32

def generate_tts(text: str, output_filename: str):
    """Generate TTS audio"""

    print(f"🎤 Generating TTS with Qwen3...")
    print(f"Speaker: {SPEAKER}")
    print(f"Device: {DEVICE}")
    print(f"Text: {text[:100]}...")

    try:
        # Initialize model and tokenizer
        print("Loading model...")
        model = Qwen3TTSModel.from_pretrained("Qwen/Qwen3-TTS-12Hz-1.7B-Base")
        tokenizer = Qwen3TTSTokenizer.from_pretrained("Qwen/Qwen3-TTS-12Hz-1.7B-Base")

        model = model.to(DEVICE).to(DTYPE)
        model.eval()

        # Generate audio
        print("Generating audio...")
        with torch.no_grad():
            audio_data = model.inference(
                text=text,
                speaker=SPEAKER,
                tokenizer=tokenizer,
                device=DEVICE
            )

        # Save
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = OUTPUT_DIR / output_filename

        # audio_data is typically a numpy array or tensor
        if isinstance(audio_data, torch.Tensor):
            audio_data = audio_data.cpu().numpy()

        sf.write(output_path, audio_data, 24000)  # Qwen3-TTS uses 24kHz

        size_kb = os.path.getsize(output_path) / 1024
        print(f"✓ Audio generated: {output_path}")
        print(f"  Size: {size_kb:.1f} KB")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: generate_vocab_audio.py <text> <output_filename>")
        sys.exit(1)

    text = sys.argv[1]
    output_file = sys.argv[2]

    success = generate_tts(text, output_file)
    sys.exit(0 if success else 1)
