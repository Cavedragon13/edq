#!/usr/bin/env python3
"""
Vocab TTS Generator - Qwen3-TTS Edition (Simplified)
=====================================================

Generates English voiceover for vocab words using Qwen3-TTS.
Uses helper script to run inside Qwen3-TTS venv.

Usage:
    vocab_tts_qwen3_v2.py --word reluctant --spelling "R-E-L-U-C-T-A-N-T"
    vocab_tts_qwen3_v2.py --test
"""

import argparse
import subprocess
import sys
from pathlib import Path

# Paths
AUDIO_OUTPUT_DIR = Path("/srv/containers/edq/projects/remotion-vocab/public/audio")
VENV_PYTHON = Path("/srv/containers/edq/venv_qwen3_tts/bin/python")
HELPER_SCRIPT = Path("/srv/containers/edq/scripts/vocab_tts_qwen3_helper.py")

# TTS Settings
DEFAULT_SPEAKER = "Aiden"  # Neutral adult male voice


def generate_script(word: str, spelling: str) -> str:
    """Generate the TTS script for a word."""
    # Convert hyphenated spelling to comma-separated for speech
    spelling_spoken = spelling.replace("-", ", ")

    script = f"""Detention vocabulary time.
Today's word is {word}.
That's {word}, spelled {spelling_spoken}.
Detention continues."""

    return script


def generate_tts(text: str, output_file: Path, speaker: str = DEFAULT_SPEAKER) -> bool:
    """
    Generate TTS using Qwen3-TTS via helper script.

    Args:
        text: Text to convert to speech
        output_file: Path to save audio file (will be WAV)
        speaker: Speaker name (Aiden, Dylan, Eric, Ryan, etc.)

    Returns:
        True if successful
    """
    # Ensure output as WAV
    if output_file.suffix.lower() != '.wav':
        output_file = output_file.with_suffix('.wav')

    output_file.parent.mkdir(parents=True, exist_ok=True)

    print(f"  🎤 Speaker: {speaker}")
    print(f"  📝 Text length: {len(text)} characters")
    print(f"  ⏳ Generating audio via Qwen3-TTS venv...")

    try:
        result = subprocess.run(
            [str(VENV_PYTHON), str(HELPER_SCRIPT),
             "--text", text,
             "--speaker", speaker,
             "--output", str(output_file)],
            capture_output=True,
            text=True,
            timeout=120
        )

        # Parse stderr for progress messages
        if result.stderr:
            for line in result.stderr.split('\n'):
                if line.startswith('SUCCESS:'):
                    parts = line.split(':')
                    if len(parts) >= 3:
                        size_kb = parts[2].strip()
                        print(f"  ✓ Audio generated: {output_file.name}")
                        print(f"  📦 File size: {size_kb} KB")
                        return True
                elif line.startswith('ERROR:'):
                    print(f"  ❌ {line[6:]}")  # Print error without "ERROR:" prefix
                elif line.strip() and not line.startswith('Traceback'):
                    # Show other progress messages
                    print(f"  {line}")

        # Check if file exists even if no SUCCESS message
        if result.returncode == 0 and output_file.exists():
            size_kb = output_file.stat().st_size / 1024
            print(f"  ✓ Audio generated: {output_file.name}")
            print(f"  📦 File size: {size_kb:.1f} KB")
            return True

        # Failed
        print(f"  ❌ Generation failed (exit code {result.returncode})")
        return False

    except subprocess.TimeoutExpired:
        print(f"  ❌ Generation timed out (>120s)")
        return False

    except FileNotFoundError:
        print(f"  ❌ Qwen3-TTS venv not found")
        print(f"  💡 Expected at: {VENV_PYTHON}")
        print(f"  💡 Run: bash /srv/containers/edq/scripts/start_qwen3_tts.sh")
        return False

    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Vocab TTS Generator (Qwen3-TTS - Simplified)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate TTS for a vocab word
  %(prog)s --word reluctant --spelling "R-E-L-U-C-T-A-N-T"

  # Use a different speaker
  %(prog)s --word reluctant --spelling "R-E-L-U-C-T-A-N-T" --speaker Ryan

  # Quick test
  %(prog)s --test

Available Speakers:
  Aiden (default), Dylan, Eric, Ryan, Serena, Sohee, Uncle_fu, Vivian, Ono_anna
        """
    )

    parser.add_argument("--word", help="Vocabulary word")
    parser.add_argument("--spelling", help="Hyphenated spelling (e.g., 'R-E-L-U-C-T-A-N-T')")
    parser.add_argument("--speaker", default=DEFAULT_SPEAKER, help=f"Speaker voice (default: {DEFAULT_SPEAKER})")
    parser.add_argument("--output", help="Custom output filename (optional)")
    parser.add_argument("--test", action="store_true", help="Run quick test")

    args = parser.parse_args()

    # Quick test
    if args.test:
        print("🧪 Running quick test...\n")
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
