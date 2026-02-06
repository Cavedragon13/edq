#!/usr/bin/env python3
"""
Vocab Video Renderer
====================

Renders vocab clips using Remotion from database entries.

Usage:
    vocab_render.py --word reluctant
    vocab_render.py --week 1
    vocab_render.py --batch week_01.json
"""

import json
import argparse
import subprocess
from pathlib import Path
from typing import Dict

# Paths
DB_FILE = Path("/srv/containers/edq/data/vocab_database.json")
REMOTION_DIR = Path("/srv/containers/edq/projects/remotion-vocab")
OUTPUT_DIR = Path("/srv/containers/edq/media/vocab_output")
TTS_OUTPUT_DIR = Path("/srv/containers/edq/ai_generated/fish_speech")  # Or qwen3-tts

def load_database() -> Dict:
    """Load the word database."""
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def find_word(db: Dict, word_id: str) -> Dict:
    """Find a word by ID."""
    for word in db["words"]:
        if word["id"].lower() == word_id.lower():
            return word
    return None


def render_word(word_data: Dict, output_path: Path = None):
    """Render a single word using Remotion."""
    word_id = word_data["id"]
    print(f"🎬 Rendering: {word_data['word']} (Week {word_data['week']}, {word_data['day']})")

    # Prepare props for Remotion
    props = {
        "word": word_data["word"],
        "spelling": word_data["spelling"],
        "microContext": word_data["micro_context_en"],
        "characterImage": f"characters/ren_{word_data['day'].lower()}.png",
        "audioFile": f"audio/{word_id}.mp3",
        "day": word_data["day"],
        "week": word_data["week"]
    }

    # Default output path
    if not output_path:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = OUTPUT_DIR / f"week{word_data['week']:02d}_{word_data['day']}_{word_id}.mp4"

    # Convert props to JSON string for CLI
    props_json = json.dumps(props)

    # Build Remotion render command
    cmd = [
        "npx", "remotion", "render",
        "VocabClip",
        str(output_path),
        "--props", props_json
    ]

    print(f"  Output: {output_path}")

    # Run render
    try:
        result = subprocess.run(
            cmd,
            cwd=REMOTION_DIR,
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode == 0:
            print(f"  ✓ Rendered successfully!")
            print(f"    File: {output_path}")
            return True
        else:
            print(f"  ❌ Render failed:")
            print(result.stderr[-500:])  # Last 500 chars of error
            return False

    except subprocess.TimeoutExpired:
        print(f"  ❌ Render timed out (5 min limit)")
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def render_week(week: int):
    """Render all words in a specific week."""
    db = load_database()
    week_words = [w for w in db["words"] if w["week"] == week]

    if not week_words:
        print(f"❌ No words found for week {week}")
        return False

    print(f"\n=== Rendering Week {week} ({len(week_words)} words) ===\n")

    success_count = 0
    for word_data in week_words:
        if render_word(word_data):
            success_count += 1
        print()

    print(f"✓ Completed: {success_count}/{len(week_words)} renders successful")
    return success_count == len(week_words)


def check_prerequisites():
    """Check if all required files exist."""
    issues = []

    if not REMOTION_DIR.exists():
        issues.append(f"Remotion project not found: {REMOTION_DIR}")

    if not DB_FILE.exists():
        issues.append(f"Database not found: {DB_FILE}")

    # Check for placeholder character images
    char_dir = REMOTION_DIR / "public" / "characters"
    if not char_dir.exists():
        issues.append(f"Characters directory not found: {char_dir}")

    # Check for audio directory
    audio_dir = REMOTION_DIR / "public" / "audio"
    if not audio_dir.exists():
        issues.append(f"Audio directory not found: {audio_dir}")

    if issues:
        print("❌ Prerequisites missing:")
        for issue in issues:
            print(f"  - {issue}")
        return False

    print("✓ Prerequisites OK")
    return True


def main():
    parser = argparse.ArgumentParser(description="Vocab Video Renderer")
    parser.add_argument("--word", help="Render a single word by ID")
    parser.add_argument("--week", type=int, help="Render all words in a week")
    parser.add_argument("--check", action="store_true", help="Check prerequisites only")

    args = parser.parse_args()

    # Check prerequisites
    if args.check:
        check_prerequisites()
        return

    if not check_prerequisites():
        print("\n⚠️  Fix prerequisites before rendering")
        return

    # Load database
    db = load_database()

    # Single word render
    if args.word:
        word_data = find_word(db, args.word)
        if not word_data:
            print(f"❌ Word '{args.word}' not found in database")
            return
        render_word(word_data)
        return

    # Week render
    if args.week:
        render_week(args.week)
        return

    # No args provided
    parser.print_help()


if __name__ == "__main__":
    main()
