#!/usr/bin/env python3
"""
Goofy Character Generator for Vocab Videos
===========================================

Generates Pixar/Illumination-style animated characters for vocabulary videos.
Uses Z-Image Base for high-quality character generation.

Usage:
    python3 vocab_character_goofy.py --type male --seed 42
    python3 vocab_character_goofy.py --type female --seed 43
"""

import argparse
import sys
from pathlib import Path
import shutil
import requests

try:
    from gradio_client import Client
except ImportError:
    print("❌ gradio_client not installed")
    print("Install with: pip install gradio_client")
    sys.exit(1)

# Configuration
ZIMAGE_URL = "http://127.0.0.1:8011/"
OUTPUT_DIR = Path("/srv/containers/edq/projects/remotion-vocab/public/characters")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Character prompts
MALE_PROMPT = """Goofy animated 3D character design, friendly young male vocabulary tutor helper.
Messy brown hair, round glasses, bright orange sweater, holding flashcards.
Pixar animation style, exaggerated friendly features, warm smile, expressive eyes.
Educational classroom background with alphabet posters.
9:16 portrait format, vibrant colors, soft lighting."""

FEMALE_PROMPT = """Goofy animated 3D character design, enthusiastic young female student helper.
Braided hair, bright eyes, teal hoodie, holding notebook with doodles.
Pixar animation style, excited 'I get it!' expression, warm smile.
Study desk background with sticky notes and coffee mug.
9:16 portrait format, vibrant colors, soft lighting."""

NEGATIVE_PROMPT = "photorealistic, realistic, anime, manga, chibi, sexy, attractive, dark, moody, detention, tired, sad, blurry, low quality, distorted, deformed, ugly, text, watermark"


def check_service():
    """Check if Z-Image Base is running."""
    try:
        response = requests.get(ZIMAGE_URL, timeout=5)
        return response.status_code == 200
    except Exception:
        return False


def generate_character(char_type: str, seed: int = -1, output_path: Path = None):
    """Generate a goofy character using Z-Image Base."""

    # Select prompt based on type
    if char_type.lower() == "male":
        prompt = MALE_PROMPT
        default_name = "male_max.png"
    elif char_type.lower() == "female":
        prompt = FEMALE_PROMPT
        default_name = "female_luna.png"
    else:
        raise ValueError(f"Unknown character type: {char_type}. Use 'male' or 'female'.")

    # Set output path
    if not output_path:
        output_path = OUTPUT_DIR / default_name

    print(f"🎨 Generating {char_type} character...")
    print(f"   Prompt: {prompt[:60]}...")
    print(f"   Seed: {seed}")
    print(f"   Output: {output_path}")
    print()

    # Connect to Z-Image Base
    try:
        client = Client(ZIMAGE_URL)
    except Exception as e:
        print(f"❌ Failed to connect to Z-Image Base: {e}")
        print(f"   Make sure Z-Image is running at {ZIMAGE_URL}")
        print(f"   Start with: bash /srv/containers/edq/scripts/start_zimage.sh")
        sys.exit(1)

    # Generate image
    try:
        print("⏳ Generating character (this may take 30-60 seconds)...")
        result = client.predict(
            prompt=prompt,
            negative_prompt=NEGATIVE_PROMPT,
            model_type="Base",  # Use Base model for quality
            controlnet_condition="None",  # No ControlNet for this task
            control_image=None,  # Required parameter even when not using ControlNet
            controlnet_scale=0.8,  # Default value (not used when condition=None)
            aspect_ratio="9:16 Portrait (576x1024)",
            width=576,
            height=1024,
            guidance_scale=7.5,  # Base model recommended range
            num_inference_steps=30,
            seed=seed,
            lora_name="None",
            lora_scale=1.0,
            api_name="/generate_image"
        )

        # Extract image path from result
        # Z-Image Base returns: (image_data, status_message)
        if isinstance(result, tuple) and len(result) >= 1:
            image_data = result[0]
        else:
            image_data = result

        # Handle different return formats
        if isinstance(image_data, dict) and 'name' in image_data:
            temp_file = image_data['name']
        elif isinstance(image_data, str):
            temp_file = image_data
        else:
            raise ValueError(f"Unexpected result format: {type(image_data)}")

        # Copy to final location
        shutil.copy(temp_file, output_path)

        print(f"✓ Character generated successfully!")
        print(f"  File: {output_path}")
        print(f"  Size: {output_path.stat().st_size / 1024:.1f} KB")

        return output_path

    except Exception as e:
        print(f"❌ Generation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Generate goofy animated characters for vocab videos"
    )
    parser.add_argument(
        "--type",
        required=True,
        choices=["male", "female"],
        help="Character type: male or female"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=-1,
        help="Random seed for reproducibility (-1 for random)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output file path (default: public/characters/{type}_{name}.png)"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if Z-Image Base is running"
    )

    args = parser.parse_args()

    # Check service
    if args.check or not check_service():
        if check_service():
            print("✓ Z-Image Base is running")
            if args.check:
                return
        else:
            print("❌ Z-Image Base is not running")
            print("   Start with: bash /srv/containers/edq/scripts/start_zimage.sh")
            print("   Note: Requires ~13-14GB VRAM (close other GPU services first)")
            sys.exit(1)

    # Generate character
    generate_character(args.type, args.seed, args.output)


if __name__ == "__main__":
    main()
