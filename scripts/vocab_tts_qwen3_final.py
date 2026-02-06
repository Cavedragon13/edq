#!/usr/bin/env python3
"""
Vocab TTS Generator - Qwen3-TTS Edition (Final)
================================================

Generates English voiceover for vocab words using Qwen3-TTS Gradio API.
Uses the already-running Qwen3-TTS service (port 8009).

Usage:
    vocab_tts_qwen3_final.py --word reluctant --spelling "R-E-L-U-C-T-A-N-T"
    vocab_tts_qwen3_final.py --test
"""

import argparse
import shutil
import sys
from pathlib import Path

# Paths
AUDIO_OUTPUT_DIR = Path("/srv/containers/edq/projects/remotion-vocab/public/audio")
QWEN_TTS_URL = "http://127.0.0.1:8009"

# TTS Settings
DEFAULT_SPEAKER = "Aiden"  # Neutral adult male voice
DEFAULT_LANGUAGE = "English"


def generate_script(word: str, spelling: str) -> str:
    """Generate the TTS script for a word."""
    spelling_spoken = spelling.replace("-", ", ")

    script = f"""Detention vocabulary time.
Today's word is {word}.
That's {word}, spelled {spelling_spoken}.
Detention continues."""

    return script


def generate_tts(text: str, output_file: Path, speaker: str = DEFAULT_SPEAKER) -> bool:
    """
    Generate TTS using Qwen3-TTS Gradio API.

    Args:
        text: Text to convert to speech
        output_file: Path to save audio file
        speaker: Speaker name

    Returns:
        True if successful
    """
    try:
        from gradio_client import Client

        print(f"  🔗 Connecting to Qwen3-TTS at {QWEN_TTS_URL}")
        client = Client(QWEN_TTS_URL)

        print(f"  🎤 Speaker: {speaker}")
        print(f"  📝 Text length: {len(text)} characters")
        print(f"  ⏳ Generating audio...")

        # Call the TTS endpoint
        # Inputs: [text, language, speaker, instruct]
        result = client.predict(
            text=text,
            language=DEFAULT_LANGUAGE,
            speaker=speaker,
            instruct="",  # No style instructions for neutral delivery
            api_name="/generate_tts"
        )

        # Result is a tuple: (audio_data, file_path_string)
        # audio_data is (sample_rate, numpy_array)
        # file_path_string is the path to the saved file
        if not result or len(result) < 2:
            print(f"  ❌ Unexpected result format: {result}")
            return False

        audio_data, file_path = result

        # file_path might be a string or a dict
        if isinstance(file_path, dict) and 'name' in file_path:
            temp_file = file_path['name']
        elif isinstance(file_path, str):
            temp_file = file_path
        else:
            print(f"  ❌ Could not extract file path from: {file_path}")
            return False

        # Copy the file to output location
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Ensure WAV extension
        if output_file.suffix.lower() != '.wav':
            output_file = output_file.with_suffix('.wav')
            print(f"  ℹ️ Saving as WAV (Remotion supports WAV)")

        shutil.copy(temp_file, output_file)

        size_kb = output_file.stat().st_size / 1024
        print(f"  ✓ Audio generated: {output_file.name}")
        print(f"  📦 File size: {size_kb:.1f} KB")

        return True

    except ImportError:
        print(f"  ❌ gradio_client not found in venv")
        print(f"  💡 This script uses: /srv/containers/edq/venv_vocab_automation")
        print(f"  💡 Run with: /srv/containers/edq/venv_vocab_automation/bin/python3 {__file__}")
        return False

    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_qwen3_tts() -> bool:
    """Check if Qwen3-TTS service is running."""
    try:
        import requests
        response = requests.get(QWEN_TTS_URL, timeout=5)
        if response.status_code == 200:
            print(f"✓ Qwen3-TTS is running at {QWEN_TTS_URL}")
            return True
        else:
            print(f"⚠️ Qwen3-TTS returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Qwen3-TTS not reachable: {e}")
        print(f"\n💡 Start it with:")
        print(f"   bash /srv/containers/edq/scripts/start_qwen3_tts.sh")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Vocab TTS Generator (Qwen3-TTS)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate TTS for a vocab word
  %(prog)s --word reluctant --spelling "R-E-L-U-C-T-A-N-T"

  # Use a different speaker
  %(prog)s --word reluctant --spelling "R-E-L-U-C-T-A-N-T" --speaker Ryan

  # Quick test
  %(prog)s --test

  # Check service status
  %(prog)s --check

Available Speakers:
  Aiden (default), Dylan, Eric, Ryan, Serena, Sohee, Uncle_fu, Vivian, Ono_anna
        """
    )

    parser.add_argument("--word", help="Vocabulary word")
    parser.add_argument("--spelling", help="Hyphenated spelling (e.g., 'R-E-L-U-C-T-A-N-T')")
    parser.add_argument("--speaker", default=DEFAULT_SPEAKER, help=f"Speaker voice (default: {DEFAULT_SPEAKER})")
    parser.add_argument("--output", help="Custom output filename")
    parser.add_argument("--test", action="store_true", help="Run quick test")
    parser.add_argument("--check", action="store_true", help="Check service status")

    args = parser.parse_args()

    # Check service status
    if args.check:
        check_qwen3_tts()
        return

    # Check service before proceeding
    if not check_qwen3_tts():
        sys.exit(1)

    # Quick test
    if args.test:
        print("\n🧪 Running quick test...\n")
        test_text = "Detention vocabulary time. Today's word is test. That's test, spelled T, E, S, T. Detention continues."
        output_file = AUDIO_OUTPUT_DIR / "test_output.wav"

        success = generate_tts(test_text, output_file, args.speaker)

        if success:
            print(f"\n✓ Test successful!")
            print(f"  Output: {output_file}")
        else:
            print(f"\n❌ Test failed")
            sys.exit(1)
        return

    # Validate required args
    if not args.word or not args.spelling:
        parser.print_help()
        print("\n❌ Error: --word and --spelling are required")
        sys.exit(1)

    # Generate script
    word = args.word.lower()
    script = generate_script(args.word, args.spelling)

    print(f"\n🎤 Generating TTS for: {args.word}")
    print(f"\n--- Script ---")
    print(script)
    print(f"--- End Script ---\n")

    # Determine output path
    if args.output:
        output_file = Path(args.output)
    else:
        output_file = AUDIO_OUTPUT_DIR / f"{word}.wav"

    # Generate TTS
    success = generate_tts(script, output_file, args.speaker)

    if success:
        print(f"\n✓ TTS generation complete!")
        print(f"  Output: {output_file}")
        print(f"  Ready for Remotion rendering")
    else:
        print(f"\n❌ TTS generation failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
