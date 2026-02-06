#!/usr/bin/env python3
"""
Vocab Batch Processor - Week 1
================================

Processes 4 words for Week 1 (Mon-Thu):
1. Generate TTS audio for each word
2. Render video with appropriate day character
3. Save outputs to organized folders

Usage:
    vocab_batch_week1.py
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime

# Paths
VOCAB_JSON = Path("/srv/containers/edq/projects/remotion-vocab/test_vocab.JSON")
REMOTION_DIR = Path("/srv/containers/edq/projects/remotion-vocab")
OUTPUT_DIR = Path(os.path.expanduser("~/ai_generated/vocab-week1"))
TTS_SCRIPT = Path("/srv/containers/edq/scripts/vocab_tts_qwen3_final.py")
VENV_PYTHON = Path("/srv/containers/edq/venv_vocab_automation/bin/python3")

# Week 1 mapping (Mon-Thu)
WEEK1_DAYS = ["Mon", "Tue", "Wed", "Thu"]
WEEK1_CHARACTERS = {
    "Mon": "monday.png",
    "Tue": "tuesday.png",
    "Wed": "wednesday.png",
    "Thu": "thursday.png",
}


def spell_word(word: str) -> str:
    """Convert word to hyphenated spelling format."""
    # Handle multi-word phrases
    if " " in word:
        # For phrases, just spell the main word
        main_word = word.split()[0]
        return "-".join(main_word.upper())

    # Single word - spell it out
    return "-".join(word.upper())


def clean_word_for_filename(word: str) -> str:
    """Convert word to safe filename."""
    return word.lower().replace(" ", "_").replace("'", "")


def generate_tts(word: str, spelling: str) -> bool:
    """Generate TTS audio for a word."""
    print(f"\n🎤 Generating TTS: {word}")

    try:
        result = subprocess.run(
            [
                str(VENV_PYTHON),
                str(TTS_SCRIPT),
                "--word", word.lower(),
                "--spelling", spelling
            ],
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode == 0:
            print(f"  ✓ TTS generated for {word}")
            return True
        else:
            print(f"  ❌ TTS failed: {result.stderr[:200]}")
            return False

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def render_video(word: str, meaning: str, day: str, week: int = 1) -> tuple[Path, bool]:
    """Render video for a word."""
    print(f"\n🎬 Rendering video: {word} ({day})")

    word_filename = clean_word_for_filename(word)
    spelling = spell_word(word)
    character = WEEK1_CHARACTERS[day]

    # Prepare Remotion props
    props = {
        "word": word,
        "spelling": spelling,
        "microContext": meaning[:50],  # Keep it short
        "characterImage": f"characters/{character}",
        "audioFile": f"audio/{word_filename}.wav",
        "day": day,
        "week": week
    }

    # Output filename
    output_file = OUTPUT_DIR / f"week{week}_{day.lower()}_{word_filename}.mp4"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    try:
        # Run Remotion render
        cmd = [
            "npx", "remotion", "render",
            "VocabClip",
            str(output_file),
            "--props", json.dumps(props)
        ]

        result = subprocess.run(
            cmd,
            cwd=str(REMOTION_DIR),
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode == 0 and output_file.exists():
            size_mb = output_file.stat().st_size / 1024 / 1024
            print(f"  ✓ Video rendered: {output_file.name} ({size_mb:.1f}MB)")
            return output_file, True
        else:
            print(f"  ❌ Render failed")
            if result.stderr:
                print(f"  Error: {result.stderr[:200]}")
            return None, False

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None, False


def main():
    print("🎭 Vocab Batch Processor - Week 1")
    print("=" * 60)

    # Load vocab list
    if not VOCAB_JSON.exists():
        print(f"❌ Vocab file not found: {VOCAB_JSON}")
        sys.exit(1)

    with open(VOCAB_JSON, 'r') as f:
        vocab_list = json.load(f)

    print(f"\n📚 Loaded {len(vocab_list)} words")

    # Extract Week 1 words (first 4)
    week1_words = vocab_list[:4]

    print(f"\n📅 Week 1 Schedule:")
    for i, (day, word_data) in enumerate(zip(WEEK1_DAYS, week1_words)):
        word = word_data['word']
        print(f"  {day}: {word}")

    # Check prerequisites
    print(f"\n🔍 Checking Prerequisites...")

    # Check TTS script
    if not TTS_SCRIPT.exists():
        print(f"❌ TTS script not found: {TTS_SCRIPT}")
        sys.exit(1)
    print(f"  ✓ TTS script ready")

    # Check Remotion
    if not REMOTION_DIR.exists():
        print(f"❌ Remotion directory not found: {REMOTION_DIR}")
        sys.exit(1)
    print(f"  ✓ Remotion project ready")

    # Check characters
    char_dir = REMOTION_DIR / "public" / "characters"
    for day, char_file in WEEK1_CHARACTERS.items():
        if not (char_dir / char_file).exists():
            print(f"❌ Character missing: {char_file}")
            sys.exit(1)
    print(f"  ✓ All characters present")

    # Process each word
    print(f"\n{'='*60}")
    print(f"Starting Batch Processing...")
    print(f"{'='*60}")

    results = []

    for i, (day, word_data) in enumerate(zip(WEEK1_DAYS, week1_words), 1):
        word = word_data['word']
        meaning = word_data['meaning']

        print(f"\n[{i}/4] Processing: {word} ({day})")
        print(f"-" * 60)

        # Step 1: Generate TTS
        spelling = spell_word(word)
        tts_success = generate_tts(word, spelling)

        if not tts_success:
            print(f"⚠️ Skipping video render due to TTS failure")
            results.append({
                'day': day,
                'word': word,
                'tts': False,
                'video': False,
                'output': None
            })
            continue

        # Step 2: Render video
        output_file, video_success = render_video(word, meaning, day, week=1)

        results.append({
            'day': day,
            'word': word,
            'tts': tts_success,
            'video': video_success,
            'output': output_file
        })

    # Summary
    print(f"\n{'='*60}")
    print(f"Batch Processing Complete!")
    print(f"{'='*60}")

    successful = sum(1 for r in results if r['video'])

    print(f"\n📊 Results: {successful}/4 videos rendered successfully")
    print(f"\n📁 Output Directory: {OUTPUT_DIR}")
    print(f"\nGenerated Videos:")

    for result in results:
        status = "✓" if result['video'] else "✗"
        print(f"  {status} {result['day']}: {result['word']}")
        if result['output']:
            print(f"      {result['output'].name}")

    if successful == 4:
        print(f"\n🎉 Week 1 Complete! All 4 videos ready for upload.")
    else:
        print(f"\n⚠️ Some videos failed. Check errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
