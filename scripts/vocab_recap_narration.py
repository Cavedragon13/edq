#!/usr/bin/env python3
"""
Vocab Recap Narration Generator
================================

Generates narration for weekly recap videos using Qwen3-TTS.
Creates energetic, engaging narration for quick-fire recaps.

Usage:
    vocab_recap_narration.py --week 4 --words "word1,word2,word3,word4" --output week4_recap.wav
"""

import argparse
import sys
from pathlib import Path
from gradio_client import Client

# Paths
QWEN_TTS_URL = "http://127.0.0.1:8009"
DEFAULT_SPEAKER = "Ryan"  # Energetic male voice
DEFAULT_LANGUAGE = "English"


def generate_recap_narration(week: int, words: list[str], output_file: Path) -> bool:
    """
    Generate recap narration using Qwen3-TTS.

    Args:
        week: Week number
        words: List of words to recap
        output_file: Output WAV file path

    Returns:
        True if successful, False otherwise
    """
    print(f"\n🎙️ Generating Week {week} Recap Narration")
    print(f"=" * 60)

    # Create energetic narration script
    words_str = ", ".join(words[:-1]) + f", and {words[-1]}" if len(words) > 1 else words[0]

    narration = f"""
    Week {week} recap! This week we learned: {words_str}.
    Let's review them quickly!
    """.strip()

    print(f"  📝 Script: {narration}")
    print(f"  🎤 Speaker: {DEFAULT_SPEAKER}")
    print(f"  🌐 Language: {DEFAULT_LANGUAGE}")

    try:
        print(f"  🔗 Connecting to Qwen3-TTS service...")
        client = Client(QWEN_TTS_URL)

        print(f"  ⏳ Generating narration...")
        result = client.predict(
            text=narration,
            language=DEFAULT_LANGUAGE,
            speaker=DEFAULT_SPEAKER,
            instruct="",  # No custom instructions
            api_name="/generate_tts"
        )

        # Result format: (audio_data, file_path_string)
        if not result or len(result) < 2:
            print(f"  ❌ Unexpected result format")
            return False

        audio_data, temp_file_str = result

        # Copy to output location
        import shutil
        temp_file = Path(temp_file_str) if isinstance(temp_file_str, str) else temp_file_str

        if not temp_file.exists():
            print(f"  ❌ Temp file not found: {temp_file}")
            return False

        output_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(temp_file, output_file)

        size_kb = output_file.stat().st_size / 1024
        print(f"  ✓ Narration generated!")
        print(f"  📦 Size: {size_kb:.1f} KB")
        print(f"  📁 Output: {output_file}")

        return True

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Generate narration for vocab recap videos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate Week 4 recap narration
  %(prog)s --week 4 --words "Spill the tea,Eloquent,Resilient,Nuance" --output week4_recap.wav

  # Custom output location
  %(prog)s --week 2 --words "word1,word2,word3,word4" --output /path/to/output.wav
        """
    )

    parser.add_argument(
        "--week",
        "-w",
        type=int,
        required=True,
        help="Week number"
    )
    parser.add_argument(
        "--words",
        required=True,
        help="Comma-separated list of words"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        required=True,
        help="Output WAV file path"
    )

    args = parser.parse_args()

    # Parse words
    words = [w.strip() for w in args.words.split(",")]

    if len(words) == 0:
        parser.error("No words provided")

    print(f"\n📚 Words: {', '.join(words)}")

    # Generate narration
    success = generate_recap_narration(args.week, words, args.output)

    if success:
        print(f"\n✓ Week {args.week} recap narration ready!")
        sys.exit(0)
    else:
        print(f"\n❌ Failed to generate narration")
        sys.exit(1)


if __name__ == "__main__":
    main()
