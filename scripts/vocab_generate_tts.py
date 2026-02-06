#!/usr/bin/env python3
"""
Vocab TTS Generator
===================

Generates English voiceover for vocab words using Fish Speech TTS.

Usage:
    vocab_generate_tts.py --word reluctant
    vocab_generate_tts.py --week 1
"""

import argparse
import json
import requests
from pathlib import Path
from typing import Dict

# Paths
DB_FILE = Path("/srv/containers/edq/data/vocab_database.json")
AUDIO_OUTPUT_DIR = Path("/srv/containers/edq/projects/remotion-vocab/public/audio")
FISH_SPEECH_URL = "http://127.0.0.1:8003"

# TTS Settings
SPEAKER = "english"  # Fish Speech default English speaker
SPEED = 1.0  # Normal speed


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


def generate_script(word_data: Dict) -> str:
    """Generate the TTS script for a word."""
    word = word_data["word"]
    spelling = word_data["spelling"].replace("-", ", ")  # R, E, L, U, C, T, A, N, T

    script = f"""Detention vocabulary time.
Today's word is {word}.
That's {word}, spelled {spelling}.
Detention continues."""

    return script


def generate_tts_gradio(text: str, output_file: Path) -> bool:
    """
    Generate TTS audio using Fish Speech Gradio API.

    Fish Speech typically runs a Gradio interface on port 8003.
    We'll use the Gradio API client to call it.
    """
    try:
        from gradio_client import Client

        print(f"  Connecting to Fish Speech at {FISH_SPEECH_URL}")
        client = Client(FISH_SPEECH_URL)

        print(f"  Generating audio...")
        print(f"  Text: {text[:100]}...")

        # Call the TTS endpoint
        # Fish Speech typically has a "TTS" or similar endpoint
        # Adjust the API call based on actual Gradio interface
        result = client.predict(
            text=text,
            speaker="english",  # Default English speaker
            api_name="/tts"  # This may vary - check Gradio interface
        )

        # Result is typically a file path
        if isinstance(result, str) and Path(result).exists():
            # Copy to output location
            import shutil
            shutil.copy(result, output_file)
            print(f"  ✓ Audio generated: {output_file}")
            return True
        else:
            print(f"  ❌ Unexpected result format: {result}")
            return False

    except ImportError:
        print("  ⚠️  gradio_client not installed, falling back to direct API")
        return generate_tts_direct(text, output_file)
    except Exception as e:
        print(f"  ❌ Gradio API error: {e}")
        print(f"  Trying direct API approach...")
        return generate_tts_direct(text, output_file)


def generate_tts_direct(text: str, output_file: Path) -> bool:
    """
    Generate TTS using direct HTTP API calls.
    Fallback method if Gradio client doesn't work.
    """
    try:
        # For Fish Speech, we might need to use the raw API
        # This is a simplified approach - may need adjustment

        # Try to find the API endpoint
        api_url = f"{FISH_SPEECH_URL}/api/v1/tts"

        payload = {
            "text": text,
            "speaker": "english",
            "speed": SPEED
        }

        print(f"  Calling TTS API: {api_url}")
        response = requests.post(api_url, json=payload, timeout=60)

        if response.status_code == 200:
            # Save audio
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'wb') as f:
                f.write(response.content)
            print(f"  ✓ Audio generated: {output_file}")
            return True
        else:
            print(f"  ❌ API error: {response.status_code}")
            print(f"  Response: {response.text[:200]}")
            return False

    except Exception as e:
        print(f"  ❌ Direct API error: {e}")
        return False


def generate_word_audio(word_data: Dict) -> bool:
    """Generate TTS audio for a single word."""
    word_id = word_data["id"]
    word = word_data["word"]

    print(f"🎤 Generating TTS for: {word}")

    # Generate script
    script = generate_script(word_data)
    print(f"\n--- Script ---")
    print(script)
    print(f"--- End Script ---\n")

    # Output path
    output_file = AUDIO_OUTPUT_DIR / f"{word_id}.mp3"

    # Generate TTS
    success = generate_tts_gradio(script, output_file)

    if success and output_file.exists():
        # Check file size
        size_kb = output_file.stat().st_size / 1024
        print(f"  File size: {size_kb:.1f} KB")
        return True
    else:
        print(f"  ❌ Failed to generate audio")
        return False


def generate_week_audio(week: int):
    """Generate TTS for all words in a week."""
    db = load_database()
    week_words = [w for w in db["words"] if w["week"] == week]

    if not week_words:
        print(f"❌ No words found for week {week}")
        return False

    print(f"\n=== Generating TTS for Week {week} ({len(week_words)} words) ===\n")

    success_count = 0
    for word_data in week_words:
        if generate_word_audio(word_data):
            success_count += 1
        print()

    print(f"✓ Completed: {success_count}/{len(week_words)} audio files generated")
    return success_count == len(week_words)


def check_fish_speech():
    """Check if Fish Speech is running."""
    try:
        response = requests.get(FISH_SPEECH_URL, timeout=5)
        if response.status_code == 200:
            print(f"✓ Fish Speech is running at {FISH_SPEECH_URL}")
            return True
        else:
            print(f"⚠️  Fish Speech returned status {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Fish Speech not reachable: {e}")
        print(f"\nStart it with:")
        print(f"  bash /srv/containers/edq/scripts/start_fish_speech.sh")
        return False


def main():
    parser = argparse.ArgumentParser(description="Vocab TTS Generator")
    parser.add_argument("--word", help="Generate TTS for a single word by ID")
    parser.add_argument("--week", type=int, help="Generate TTS for all words in a week")
    parser.add_argument("--check", action="store_true", help="Check Fish Speech status")

    args = parser.parse_args()

    # Check Fish Speech
    if args.check:
        check_fish_speech()
        return

    if not check_fish_speech():
        print("\n⚠️  Start Fish Speech before generating TTS")
        return

    # Load database
    db = load_database()

    # Single word
    if args.word:
        word_data = find_word(db, args.word)
        if not word_data:
            print(f"❌ Word '{args.word}' not found in database")
            return
        generate_word_audio(word_data)
        return

    # Week
    if args.week:
        generate_week_audio(args.week)
        return

    # No args
    parser.print_help()


if __name__ == "__main__":
    main()
