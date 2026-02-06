#!/usr/bin/env python3
"""
Helper script to be run inside Qwen3-TTS venv.
Directly generates TTS without needing Gradio API.
"""

import sys
import argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", required=True)
    parser.add_argument("--speaker", default="Aiden")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    try:
        import torch
        import soundfile as sf
        from qwen_tts import Qwen3TTSModel

        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.bfloat16 if device == "cuda" else torch.float32

        print(f"Loading Qwen3-TTS model (device: {device})...", file=sys.stderr)

        model = Qwen3TTSModel.from_pretrained(
            "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
            device_map=device,
            dtype=dtype,
        )

        print(f"Generating audio for speaker: {args.speaker}...", file=sys.stderr)

        with torch.no_grad():
            wavs, sr = model.generate_custom_voice(
                text=args.text.strip(),
                language="English",
                speaker=args.speaker.lower().replace(" ", "_"),
                instruct=None,
                non_streaming_mode=True,
                max_new_tokens=4096,
            )

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        sf.write(str(output_path), wavs, sr)

        size_kb = output_path.stat().st_size / 1024
        print(f"SUCCESS:{output_path}:{size_kb:.1f}", file=sys.stderr)

        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    except Exception as e:
        print(f"ERROR:{e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
