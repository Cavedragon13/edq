#!/usr/bin/env python3
"""
Vocab Audio Concatenation Script
==================================

Concatenates multiple WAV audio files into a single file for recap videos.
Adds brief silence between words for better pacing.

Usage:
    vocab_audio_concat.py word1.wav word2.wav word3.wav word4.wav output.wav
    vocab_audio_concat.py --silence 0.5 word1.wav word2.wav output.wav
"""

import sys
import argparse
from pathlib import Path
from pydub import AudioSegment


def concatenate_audio(input_files: list[Path], output_file: Path, silence_ms: int = 300):
    """
    Concatenate multiple audio files with silence between them.

    Args:
        input_files: List of input WAV file paths
        output_file: Output WAV file path
        silence_ms: Milliseconds of silence between files (default: 300ms)
    """
    print(f"\n🎵 Audio Concatenation")
    print(f"=" * 60)

    # Load all audio files
    audio_segments = []
    for i, file_path in enumerate(input_files, 1):
        if not file_path.exists():
            print(f"  ❌ File not found: {file_path}")
            sys.exit(1)

        print(f"  [{i}/{len(input_files)}] Loading: {file_path.name}")
        audio = AudioSegment.from_wav(str(file_path))
        audio_segments.append(audio)

    # Create silence segment
    silence = AudioSegment.silent(duration=silence_ms)

    # Concatenate with silence between
    print(f"\n  🔗 Concatenating with {silence_ms}ms silence between...")
    combined = audio_segments[0]

    for audio in audio_segments[1:]:
        combined += silence + audio

    # Export
    output_file.parent.mkdir(parents=True, exist_ok=True)
    print(f"  💾 Exporting: {output_file}")
    combined.export(str(output_file), format="wav")

    # Stats
    duration_sec = len(combined) / 1000
    size_kb = output_file.stat().st_size / 1024

    print(f"\n  ✓ Concatenation complete!")
    print(f"  📊 Duration: {duration_sec:.1f}s")
    print(f"  📦 Size: {size_kb:.1f} KB")
    print(f"  📁 Output: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Concatenate multiple WAV audio files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Concatenate 4 words with default 300ms silence
  %(prog)s word1.wav word2.wav word3.wav word4.wav recap.wav

  # Custom silence duration
  %(prog)s --silence 500 word1.wav word2.wav output.wav

  # Using full paths
  %(prog)s /path/to/audio/*.wav /output/recap.wav
        """
    )

    parser.add_argument(
        "files",
        nargs="+",
        help="Input WAV files followed by output file (last argument)"
    )
    parser.add_argument(
        "--silence",
        "-s",
        type=int,
        default=300,
        help="Milliseconds of silence between files (default: 300)"
    )

    args = parser.parse_args()

    if len(args.files) < 3:
        parser.error("Need at least 2 input files and 1 output file")

    # Last file is output, rest are inputs
    input_files = [Path(f) for f in args.files[:-1]]
    output_file = Path(args.files[-1])

    concatenate_audio(input_files, output_file, args.silence)


if __name__ == "__main__":
    main()
