#!/usr/bin/env python3
"""
HeartMuLa Music Generator for Vocab Videos
===========================================

Generates short instrumental background music for vocabulary videos.
Uses HeartMuLa for music generation, then trims to exact duration with ffmpeg.

Usage:
    python3 vocab_music_heartmula.py --duration 15 --style educational
    python3 vocab_music_heartmula.py --duration 30 --style upbeat
"""

import argparse
import sys
import subprocess
from pathlib import Path
import shutil
import requests
import datetime

try:
    from gradio_client import Client
except ImportError:
    print("❌ gradio_client not installed")
    print("Install with: pip install gradio_client")
    sys.exit(1)

# Configuration
HEARTMULA_URL = "http://127.0.0.1:8004/"
OUTPUT_DIR = Path("/srv/containers/edq/projects/remotion-vocab/public/music")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR = Path.home() / "ai_generated" / "heartmula"

# Style presets
STYLE_PRESETS = {
    "educational": "piano,upbeat,inspiring,educational,ambient,soft",
    "upbeat": "piano,happy,uplifting,energetic,bright",
    "calm": "piano,soft,relaxing,peaceful,gentle,ambient",
    "motivational": "piano,inspiring,hopeful,positive,encouraging"
}


def check_service():
    """Check if HeartMuLa is running."""
    try:
        response = requests.get(HEARTMULA_URL, timeout=5)
        return response.status_code == 200
    except Exception:
        return False


def check_ffmpeg():
    """Check if ffmpeg is available."""
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
        return True
    except Exception:
        return False


def generate_music(
    duration: int,
    style: str = "educational",
    custom_tags: str = None,
    output_name: str = "monday_theme.mp3"
):
    """Generate background music using HeartMuLa."""

    # HeartMuLa minimum duration is 30 seconds
    generation_duration = max(30, duration)
    needs_trimming = duration < generation_duration

    # Get style tags
    if custom_tags:
        tags = custom_tags
    else:
        tags = STYLE_PRESETS.get(style, STYLE_PRESETS["educational"])

    output_path = OUTPUT_DIR / output_name

    print(f"🎵 Generating {duration}s background music...")
    print(f"   Style: {style}")
    print(f"   Tags: {tags}")
    print(f"   Generation duration: {generation_duration}s (HeartMuLa minimum: 30s)")
    if needs_trimming:
        print(f"   Will trim to {duration}s with ffmpeg")
    print()

    # Connect to HeartMuLa
    try:
        client = Client(HEARTMULA_URL)
    except Exception as e:
        print(f"❌ Failed to connect to HeartMuLa: {e}")
        print(f"   Make sure HeartMuLa is running at {HEARTMULA_URL}")
        print(f"   Start with: bash /srv/containers/edq/scripts/start_heartmula.sh")
        print(f"   Note: Requires ~12GB VRAM (close other GPU services first)")
        sys.exit(1)

    # Generate music
    try:
        print("⏳ Generating music (this may take 1-2 minutes)...")
        print("   HeartMuLa generates at ~1x real-time speed")
        print()

        # Gradio API call - positional arguments matching generate_music function
        result = client.predict(
            "[Intro] [Instrumental] [Outro]",  # lyrics
            tags,                               # tags
            generation_duration,                # max_duration_seconds
            1.0,                                # temperature
            50,                                 # topk
            1.5                                 # cfg_scale
            # No api_name - let Gradio use default (first function)
        )

        # Extract audio path from result
        # HeartMuLa returns: file_path (string)
        if isinstance(result, str):
            temp_file = result
        elif isinstance(result, dict) and 'name' in result:
            temp_file = result['name']
        else:
            raise ValueError(f"Unexpected result format: {type(result)}")

        temp_file_path = Path(temp_file)

        if not temp_file_path.exists():
            raise FileNotFoundError(f"Generated file not found: {temp_file}")

        print(f"✓ Music generated: {temp_file}")
        print(f"  Original size: {temp_file_path.stat().st_size / 1024:.1f} KB")
        print()

        # Trim to exact duration if needed
        if needs_trimming:
            print(f"✂️  Trimming to {duration} seconds with ffmpeg...")

            # Create temporary trimmed file
            trimmed_temp = temp_file_path.parent / f"trimmed_{output_name}"

            cmd = [
                "ffmpeg", "-y",
                "-i", str(temp_file_path),
                "-t", str(duration),
                "-c", "copy",  # Fast copy, no re-encoding
                str(trimmed_temp)
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                print(f"❌ FFmpeg failed:")
                print(result.stderr[-500:])
                sys.exit(1)

            # Use trimmed file
            shutil.copy(trimmed_temp, output_path)
            trimmed_temp.unlink()  # Clean up temp
            print(f"✓ Trimmed successfully")

        else:
            # Just copy the original
            shutil.copy(temp_file_path, output_path)

        print(f"✓ Music saved to: {output_path}")
        print(f"  Final size: {output_path.stat().st_size / 1024:.1f} KB")
        print()

        return output_path

    except Exception as e:
        print(f"❌ Generation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Generate background music for vocab videos"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=15,
        help="Duration in seconds (will generate 30s minimum, then trim)"
    )
    parser.add_argument(
        "--style",
        choices=list(STYLE_PRESETS.keys()),
        default="educational",
        help="Music style preset"
    )
    parser.add_argument(
        "--tags",
        type=str,
        help="Custom comma-separated tags (overrides --style)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="monday_theme.mp3",
        help="Output filename (saved to public/music/)"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if HeartMuLa and ffmpeg are available"
    )

    args = parser.parse_args()

    # Check services
    if args.check:
        print("🔍 Checking services...")
        print()

        heartmula_ok = check_service()
        ffmpeg_ok = check_ffmpeg()

        if heartmula_ok:
            print("✓ HeartMuLa is running")
        else:
            print("❌ HeartMuLa is not running")
            print("   Start with: bash /srv/containers/edq/scripts/start_heartmula.sh")

        if ffmpeg_ok:
            print("✓ ffmpeg is available")
        else:
            print("❌ ffmpeg not found")
            print("   Install with: sudo apt install ffmpeg")

        if not (heartmula_ok and ffmpeg_ok):
            sys.exit(1)

        return

    # Verify services before generating
    if not check_service():
        print("❌ HeartMuLa is not running")
        print("   Start with: bash /srv/containers/edq/scripts/start_heartmula.sh")
        print("   Note: Requires ~12GB VRAM (close other GPU services first)")
        sys.exit(1)

    if not check_ffmpeg():
        print("❌ ffmpeg not found")
        print("   Install with: sudo apt install ffmpeg")
        sys.exit(1)

    # Generate music
    generate_music(args.duration, args.style, args.tags, args.output)


if __name__ == "__main__":
    main()
