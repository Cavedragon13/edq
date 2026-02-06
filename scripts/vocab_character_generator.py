#!/usr/bin/env python3
"""
Vocab Character Generator - Production Script
==============================================

Generates all 5 character variations (Mon-Fri) for vocab project.
Uses DragonFlux Klein via Dashboard service.
Saves directly to Remotion public/characters/ folder.

Usage:
    vocab_character_generator.py --all
    vocab_character_generator.py --day monday
    vocab_character_generator.py --all --seed 12345
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime

# Paths
CHARACTER_OUTPUT_DIR = Path("/srv/containers/edq/projects/remotion-vocab/public/characters")
DRAGONFLUX_URL = "http://127.0.0.1:8001"

# Character prompts (progressive reveal)
CHARACTER_PROMPTS = {
    "monday": {
        "frame": "extreme close-up face only",
        "description": (
            "Attractive young woman in school uniform, Monday morning detention. "
            "Extreme close-up portrait showing only face and eyes, tired but beautiful expression, "
            "subtle eye bags, soft dramatic lighting. "
            "Photorealistic style, cinematic quality, detailed facial features. "
            "Sitting at classroom desk. "
            "9:16 portrait format."
        ),
        "negative": (
            "cartoon, anime, chibi, cute style, multiple people, "
            "blurry, low quality, distorted, deformed, ugly, "
            "text, watermark, smile, happy"
        ),
    },
    "tuesday": {
        "frame": "face and shoulders visible",
        "description": (
            "Attractive young woman in school uniform, Tuesday detention. "
            "Portrait showing face, neck, and shoulders, tired expression. "
            "School uniform collar and tie partially visible. "
            "Soft dramatic lighting, photorealistic style, cinematic quality. "
            "Sitting at classroom desk. "
            "9:16 portrait format."
        ),
        "negative": "cartoon, anime, blurry, low quality, distorted, deformed, ugly, text, watermark, smile",
    },
    "wednesday": {
        "frame": "upper body and desk edge",
        "description": (
            "Attractive young woman in school uniform, Wednesday detention. "
            "Upper body portrait showing face, torso, and arms resting on desk edge. "
            "School uniform clearly visible (blazer, shirt, tie). "
            "Tired midweek expression, soft dramatic lighting. "
            "Photorealistic style, cinematic quality. "
            "9:16 portrait format."
        ),
        "negative": "cartoon, anime, blurry, low quality, distorted, deformed, ugly, text, watermark, smile",
    },
    "thursday": {
        "frame": "three-quarter view more visible",
        "description": (
            "Attractive young woman in school uniform, Thursday detention. "
            "Three-quarter view showing upper body and partial desk setup. "
            "School uniform fully visible, hands on desk. "
            "Slightly more alert expression, soft dramatic lighting. "
            "Photorealistic style, cinematic quality. "
            "9:16 portrait format."
        ),
        "negative": "cartoon, anime, blurry, low quality, distorted, deformed, ugly, text, watermark",
    },
    "friday": {
        "frame": "full body reveal",
        "description": (
            "Attractive young woman in school uniform, Friday detention. "
            "Full body shot showing entire figure and classroom desk setup. "
            "Complete school uniform visible (blazer, skirt, shoes). "
            "Slightly relieved expression (weekend coming), soft dramatic lighting. "
            "Photorealistic style, cinematic quality, detailed environment. "
            "9:16 portrait format."
        ),
        "negative": "cartoon, anime, blurry, low quality, distorted, deformed, ugly, text, watermark",
    },
}

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday"]


def check_dragonflux() -> bool:
    """Check if DragonFlux Klein is running."""
    try:
        import requests
        response = requests.get(DRAGONFLUX_URL, timeout=5)
        if response.status_code == 200:
            print(f"✓ DragonFlux Klein is running")
            return True
        else:
            print(f"⚠️ DragonFlux Klein returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ DragonFlux Klein not reachable: {e}")
        print(f"\n💡 Start it with:")
        print(f"   bash /srv/containers/edq/scripts/start_flux2_klein.sh")
        return False


def generate_character(day: str, seed: int = -1) -> tuple[Path, str]:
    """
    Generate character image for a specific day.

    Args:
        day: Day of the week (monday-friday)
        seed: Random seed for reproducibility (-1 for random)

    Returns:
        (output_path, status_message)
    """
    try:
        from gradio_client import Client

        prompt_data = CHARACTER_PROMPTS[day]
        prompt = prompt_data["description"]
        negative = prompt_data["negative"]

        print(f"\n🎨 Generating {day.capitalize()}")
        print(f"  📝 Frame: {prompt_data['frame']}")
        if seed != -1:
            print(f"  🎲 Seed: {seed} (for consistency)")
        else:
            print(f"  🎲 Seed: Random")

        client = Client(DRAGONFLUX_URL)

        result = client.predict(
            prompt=prompt,
            model_variant="FLUX.2-klein-4B (Recommended) - ~12GB",
            aspect_ratio="9:16 (Portrait)",
            width=576,
            height=1024,
            guidance_scale=1.0,
            num_inference_steps=4,
            seed=seed,
            lora_name="None",
            lora_scale=1.0,
            input_image=None,
            img2img_strength=0.75,
            api_name="/generate_image"
        )

        if not result or len(result) < 2:
            print(f"  ❌ Unexpected result format")
            return None, "Unexpected result format"

        image_data, status = result

        # Extract image file
        if isinstance(image_data, dict) and 'name' in image_data:
            temp_file = Path(image_data['name'])
        elif isinstance(image_data, str):
            temp_file = Path(image_data)
        else:
            print(f"  ❌ Could not extract image")
            return None, "Could not extract image"

        # Copy to production folder with standard naming
        CHARACTER_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_file = CHARACTER_OUTPUT_DIR / f"{day}.png"

        import shutil
        shutil.copy(temp_file, output_file)

        size_kb = output_file.stat().st_size / 1024
        print(f"  ✓ Generated: {output_file}")
        print(f"  📦 Size: {size_kb:.1f} KB")

        return output_file, status

    except ImportError:
        print(f"  ❌ gradio_client not found")
        print(f"  💡 Install with: /srv/containers/edq/venv_vocab_automation/bin/pip install gradio_client")
        return None, "gradio_client not installed"

    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None, str(e)


def main():
    parser = argparse.ArgumentParser(
        description="Generate character assets for vocab project",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate all 5 characters (Mon-Fri)
  %(prog)s --all

  # Generate with fixed seed for consistency
  %(prog)s --all --seed 42

  # Generate single day
  %(prog)s --day monday

  # Regenerate just Friday
  %(prog)s --day friday --seed 42

Output Location:
  All characters saved to: ~/projects/remotion-vocab/public/characters/
  - monday.png
  - tuesday.png
  - wednesday.png
  - thursday.png
  - friday.png
        """
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Generate all 5 character variations (Mon-Fri)"
    )
    parser.add_argument(
        "--day",
        choices=DAYS,
        help="Generate single day only"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=-1,
        help="Random seed for reproducibility (-1 for random, default: -1)"
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.all and not args.day:
        parser.print_help()
        print("\n❌ Error: Must specify --all or --day")
        sys.exit(1)

    print(f"🎭 Vocab Character Generator")
    print(f"=" * 60)
    print(f"\n📁 Output Directory:")
    print(f"   {CHARACTER_OUTPUT_DIR}")

    # Check DragonFlux Klein service
    print(f"\n🔍 Checking Services...")
    if not check_dragonflux():
        sys.exit(1)

    # Determine which days to generate
    if args.all:
        days_to_generate = DAYS
        print(f"\n📅 Generating all 5 days (Mon-Fri)")
    else:
        days_to_generate = [args.day]
        print(f"\n📅 Generating {args.day.capitalize()} only")

    if args.seed != -1:
        print(f"🎲 Using fixed seed: {args.seed} (for character consistency)")

    # Generate characters
    results = {}
    for day in days_to_generate:
        output_file, status = generate_character(day, args.seed)
        if output_file:
            results[day] = output_file

    # Summary
    print(f"\n" + "=" * 60)
    if len(results) == len(days_to_generate):
        print(f"✓ Generation Complete!")
        print(f"\n📁 Character Files:")
        for day in days_to_generate:
            if day in results:
                print(f"   ✓ {results[day].name}")
        print(f"\n📂 Location: {CHARACTER_OUTPUT_DIR}")
        print(f"💡 Files ready for Remotion rendering")
    else:
        print(f"⚠️ Partial Success")
        print(f"   Generated: {len(results)}/{len(days_to_generate)}")
        failed = set(days_to_generate) - set(results.keys())
        if failed:
            print(f"   Failed: {', '.join(failed)}")


if __name__ == "__main__":
    main()
