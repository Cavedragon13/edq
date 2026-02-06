#!/usr/bin/env python3
"""
Vocab Batch Processor - Full 5 Weeks with Friday Recaps
========================================================

Processes all 20 words across 5 weeks with different Friday recap styles:
- Week 1: Sequential recap (concatenated TTS audio)
- Week 2: Grid recap (concatenated TTS audio)
- Week 3: Quick Fire recap (concatenated TTS audio)
- Week 4: Quick Fire recap (new narration)
- Week 5: Quick Fire recap (text only, no audio)

Usage:
    vocab_batch_full.py
    vocab_batch_full.py --week 1  # Process single week only
"""

import json
import os
import subprocess
import sys
import argparse
from pathlib import Path
from datetime import datetime

# Paths
VOCAB_JSON = Path("/srv/containers/edq/projects/remotion-vocab/test_vocab.JSON")
REMOTION_DIR = Path("/srv/containers/edq/projects/remotion-vocab")
OUTPUT_DIR = Path(os.path.expanduser("~/ai_generated/vocab-weeks"))
AUDIO_DIR = REMOTION_DIR / "public" / "audio"
TTS_SCRIPT = Path("/srv/containers/edq/scripts/vocab_tts_qwen3_final.py")
AUDIO_CONCAT_SCRIPT = Path("/srv/containers/edq/scripts/vocab_audio_concat.py")
RECAP_NARRATION_SCRIPT = Path("/srv/containers/edq/scripts/vocab_recap_narration.py")
VENV_PYTHON = Path("/srv/containers/edq/venv_vocab_automation/bin/python3")

# Week configuration
WEEK_CONFIG = {
    1: {
        "days": ["Mon", "Tue", "Wed", "Thu"],
        "recap_type": "RecapSequential",
        "recap_audio": "concatenated",
    },
    2: {
        "days": ["Mon", "Tue", "Wed", "Thu"],
        "recap_type": "RecapGrid",
        "recap_audio": "concatenated",
    },
    3: {
        "days": ["Mon", "Tue", "Wed", "Thu"],
        "recap_type": "RecapQuickFire",
        "recap_audio": "concatenated",
    },
    4: {
        "days": ["Mon", "Tue", "Wed", "Thu"],
        "recap_type": "RecapQuickFire",
        "recap_audio": "narration",
    },
    5: {
        "days": ["Mon"],  # Only 1 word left
        "recap_type": "RecapQuickFire",
        "recap_audio": "none",  # Text only
    },
}

CHARACTER_MAP = {
    "Mon": "monday.png",
    "Tue": "tuesday.png",
    "Wed": "wednesday.png",
    "Thu": "thursday.png",
    "Fri": "friday.png",
}


def spell_word(word: str) -> str:
    """Convert word to hyphenated spelling format."""
    if " " in word:
        main_word = word.split()[0]
        return "-".join(main_word.upper())
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


def concatenate_audio(week: int, words: list[str]) -> tuple[Path, bool]:
    """Concatenate word audio files for recap."""
    print(f"\n🔗 Concatenating audio for Week {week} recap")

    audio_files = []
    for word in words:
        word_filename = clean_word_for_filename(word)
        audio_file = AUDIO_DIR / f"{word_filename}.wav"
        if not audio_file.exists():
            print(f"  ❌ Audio file not found: {audio_file}")
            return None, False
        audio_files.append(audio_file)

    output_file = AUDIO_DIR / f"week{week}_recap.wav"

    try:
        result = subprocess.run(
            [
                str(VENV_PYTHON),
                str(AUDIO_CONCAT_SCRIPT),
                *[str(f) for f in audio_files],
                str(output_file)
            ],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode == 0 and output_file.exists():
            print(f"  ✓ Audio concatenated: {output_file.name}")
            return output_file, True
        else:
            print(f"  ❌ Concatenation failed")
            return None, False

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None, False


def generate_recap_narration(week: int, words: list[str]) -> tuple[Path, bool]:
    """Generate new narration for recap (Week 4)."""
    print(f"\n🎙️ Generating narration for Week {week} recap")

    output_file = AUDIO_DIR / f"week{week}_recap.wav"
    words_str = ",".join(words)

    try:
        result = subprocess.run(
            [
                str(VENV_PYTHON),
                str(RECAP_NARRATION_SCRIPT),
                "--week", str(week),
                "--words", words_str,
                "--output", str(output_file)
            ],
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode == 0 and output_file.exists():
            print(f"  ✓ Narration generated: {output_file.name}")
            return output_file, True
        else:
            print(f"  ❌ Narration generation failed")
            return None, False

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None, False


def render_video(word: str, meaning: str, day: str, week: int) -> tuple[Path, bool]:
    """Render video for a word."""
    print(f"\n🎬 Rendering video: {word} ({day})")

    word_filename = clean_word_for_filename(word)
    spelling = spell_word(word)
    character = CHARACTER_MAP[day]

    props = {
        "word": word,
        "spelling": spelling,
        "microContext": meaning[:50],
        "characterImage": f"characters/{character}",
        "audioFile": f"audio/{word_filename}.wav",
        "day": day,
        "week": week
    }

    output_file = OUTPUT_DIR / f"week{week}" / f"week{week}_{day.lower()}_{word_filename}.mp4"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    try:
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


def render_recap_video(week: int, words_data: list[dict], recap_type: str, audio_file: Path = None) -> tuple[Path, bool]:
    """Render Friday recap video."""
    print(f"\n🎬 Rendering Week {week} recap ({recap_type})")

    # Build words array for props
    recap_words = []
    for word_data in words_data:
        recap_words.append({
            "word": word_data["word"],
            "spelling": spell_word(word_data["word"]),
            "meaning": word_data["meaning"]
        })

    props = {
        "words": recap_words,
        "characterImage": "characters/friday.png",
        "week": week
    }

    # Add audio if provided
    if audio_file:
        props["audioFile"] = f"audio/{audio_file.name}"

    output_file = OUTPUT_DIR / f"week{week}" / f"week{week}_fri_recap.mp4"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        cmd = [
            "npx", "remotion", "render",
            recap_type,
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
            print(f"  ✓ Recap rendered: {output_file.name} ({size_mb:.1f}MB)")
            return output_file, True
        else:
            print(f"  ❌ Recap render failed")
            if result.stderr:
                print(f"  Error: {result.stderr[:200]}")
            return None, False

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None, False


def process_week(week: int, vocab_list: list[dict]):
    """Process all videos for a single week."""
    config = WEEK_CONFIG[week]
    start_idx = sum(len(WEEK_CONFIG[w]["days"]) for w in range(1, week))
    week_words = vocab_list[start_idx:start_idx + len(config["days"])]

    if len(week_words) < len(config["days"]):
        print(f"⚠️ Week {week}: Only {len(week_words)} words available (expected {len(config['days'])})")
        if len(week_words) == 0:
            return []

    print(f"\n{'='*60}")
    print(f"Processing Week {week}")
    print(f"{'='*60}")
    print(f"\n📅 Schedule:")
    for day, word_data in zip(config["days"], week_words):
        print(f"  {day}: {word_data['word']}")

    results = []

    # Process Mon-Thu (or however many days this week has)
    for i, (day, word_data) in enumerate(zip(config["days"], week_words), 1):
        word = word_data["word"]
        meaning = word_data["meaning"]

        print(f"\n[{i}/{len(week_words)}] Processing: {word} ({day})")
        print(f"-" * 60)

        # Generate TTS
        spelling = spell_word(word)
        tts_success = generate_tts(word, spelling)

        if not tts_success:
            print(f"⚠️ Skipping video render due to TTS failure")
            results.append({
                "week": week,
                "day": day,
                "word": word,
                "tts": False,
                "video": False,
                "output": None
            })
            continue

        # Render video
        output_file, video_success = render_video(word, meaning, day, week)

        results.append({
            "week": week,
            "day": day,
            "word": word,
            "tts": tts_success,
            "video": video_success,
            "output": output_file
        })

    # Process Friday recap
    print(f"\n[{len(week_words) + 1}/{len(week_words) + 1}] Processing: Friday Recap")
    print(f"-" * 60)

    recap_audio = None
    audio_success = True

    if config["recap_audio"] == "concatenated":
        # Concatenate TTS audio from the week
        recap_audio, audio_success = concatenate_audio(week, [w["word"] for w in week_words])

    elif config["recap_audio"] == "narration":
        # Generate new narration
        recap_audio, audio_success = generate_recap_narration(week, [w["word"] for w in week_words])

    elif config["recap_audio"] == "none":
        # No audio for Week 5
        print(f"  ℹ️ Week {week}: Text-only recap (no audio)")
        audio_success = True

    if not audio_success and config["recap_audio"] != "none":
        print(f"⚠️ Skipping recap render due to audio failure")
        results.append({
            "week": week,
            "day": "Fri",
            "word": "Recap",
            "tts": False,
            "video": False,
            "output": None
        })
    else:
        # Render recap video
        recap_output, recap_success = render_recap_video(
            week,
            week_words,
            config["recap_type"],
            recap_audio
        )

        results.append({
            "week": week,
            "day": "Fri",
            "word": "Recap",
            "tts": audio_success,
            "video": recap_success,
            "output": recap_output
        })

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Process all 5 weeks of vocab content with Friday recaps"
    )
    parser.add_argument(
        "--week",
        "-w",
        type=int,
        choices=[1, 2, 3, 4, 5],
        help="Process single week only (default: all weeks)"
    )

    args = parser.parse_args()

    print("🎭 Vocab Batch Processor - Full 5 Weeks")
    print("=" * 60)

    # Load vocab list
    if not VOCAB_JSON.exists():
        print(f"❌ Vocab file not found: {VOCAB_JSON}")
        sys.exit(1)

    with open(VOCAB_JSON, 'r') as f:
        vocab_list = json.load(f)

    print(f"\n📚 Loaded {len(vocab_list)} words")

    # Determine which weeks to process
    weeks_to_process = [args.week] if args.week else [1, 2, 3, 4, 5]

    all_results = []

    for week in weeks_to_process:
        week_results = process_week(week, vocab_list)
        all_results.extend(week_results)

    # Summary
    print(f"\n{'='*60}")
    print(f"Batch Processing Complete!")
    print(f"{'='*60}")

    successful_videos = sum(1 for r in all_results if r["video"])
    total_videos = len(all_results)

    print(f"\n📊 Results: {successful_videos}/{total_videos} videos rendered successfully")
    print(f"\n📁 Output Directory: {OUTPUT_DIR}")

    # Group by week
    for week in weeks_to_process:
        week_results = [r for r in all_results if r["week"] == week]
        if week_results:
            print(f"\nWeek {week}:")
            for result in week_results:
                status = "✓" if result["video"] else "✗"
                print(f"  {status} {result['day']}: {result['word']}")
                if result["output"]:
                    print(f"      {result['output'].name}")

    if successful_videos == total_videos:
        print(f"\n🎉 All videos rendered successfully!")
    else:
        print(f"\n⚠️ Some videos failed. Check errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
