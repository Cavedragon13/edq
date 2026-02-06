#!/usr/bin/env python3
"""
Vocab Character Generator - Test Script
========================================

Compares DragonFlux Klein vs Z-Image Base for REN character generation.
Uses Dashboard services via gradio_client (no VRAM conflicts).

Usage:
    vocab_character_test.py --day monday
    vocab_character_test.py --day monday --upscale
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime

# Paths
CHARACTER_OUTPUT_DIR = Path("/srv/containers/edq/projects/remotion-vocab/public/characters")
TEST_OUTPUT_DIR = Path("/srv/containers/edq/projects/remotion-vocab/test_characters")

# Service URLs
DRAGONFLUX_URL = "http://127.0.0.1:8001"
ZIMAGE_URL = "http://127.0.0.1:8011"
REALESRGAN_URL = "http://127.0.0.1:8010"

# Character prompts for each day (progressive framing)
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


def check_service(url: str, name: str) -> bool:
    """Check if a service is running."""
    try:
        import requests
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            print(f"✓ {name} is running")
            return True
        else:
            print(f"⚠️ {name} returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ {name} not reachable: {e}")
        return False


def generate_with_dragonflux(prompt: str, day: str) -> tuple[Path, str]:
    """Generate character using DragonFlux Klein via Dashboard service."""
    try:
        from gradio_client import Client

        print(f"\n🎨 DragonFlux Klein Generation")
        print(f"  📝 Prompt: {prompt[:80]}...")
        print(f"  🔗 Connecting to {DRAGONFLUX_URL}")

        client = Client(DRAGONFLUX_URL)

        # Function signature from flux2_klein_gradio.py:
        # generate_image(prompt, model_variant, aspect_ratio, width, height,
        #                guidance_scale, num_inference_steps, seed, lora_name, lora_scale,
        #                input_image, img2img_strength)

        print(f"  ⏳ Generating (4 steps)...")
        result = client.predict(
            prompt=prompt,
            model_variant="FLUX.2-klein-4B (Recommended) - ~12GB",  # Full display name
            aspect_ratio="9:16 (Portrait)",
            width=576,  # Ignored when aspect_ratio is preset
            height=1024,
            guidance_scale=1.0,
            num_inference_steps=4,
            seed=-1,  # Random
            lora_name="None",
            lora_scale=1.0,
            input_image=None,  # No img2img
            img2img_strength=0.75,
            api_name="/generate_image"
        )

        # Result format: (image, status_text)
        if not result or len(result) < 2:
            print(f"  ❌ Unexpected result format: {result}")
            return None, "Unexpected result format"

        image_data, status = result

        # image_data might be a file path dict or actual image
        if isinstance(image_data, dict) and 'name' in image_data:
            temp_file = Path(image_data['name'])
        elif isinstance(image_data, str):
            temp_file = Path(image_data)
        else:
            print(f"  ❌ Could not extract image from: {image_data}")
            return None, "Could not extract image"

        # Copy to test output directory
        TEST_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = TEST_OUTPUT_DIR / f"dragonflux_{day}_{timestamp}.png"

        import shutil
        shutil.copy(temp_file, output_file)

        size_kb = output_file.stat().st_size / 1024
        print(f"  ✓ Generated: {output_file.name}")
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


def generate_with_zimage(prompt: str, negative_prompt: str, day: str) -> tuple[Path, str]:
    """Generate character using Z-Image Base via Dashboard service."""
    try:
        from gradio_client import Client

        print(f"\n🎨 Z-Image Base Generation")
        print(f"  📝 Prompt: {prompt[:80]}...")
        print(f"  🚫 Negative: {negative_prompt[:60]}...")
        print(f"  🔗 Connecting to {ZIMAGE_URL}")

        client = Client(ZIMAGE_URL)

        # Function signature from zimage_base_gradio.py:
        # generate_image(prompt, negative_prompt, aspect_ratio, width, height,
        #                guidance_scale, num_inference_steps, seed, lora_name, lora_scale)

        print(f"  ⏳ Generating (30 steps, CFG 7.0)...")
        result = client.predict(
            prompt=prompt,
            negative_prompt=negative_prompt,
            aspect_ratio="9:16 Portrait (576x1024)",
            width=576,
            height=1024,
            guidance_scale=7.0,
            num_inference_steps=30,
            seed=-1,
            lora_name="None",
            lora_scale=1.0,
            api_name="/generate_image"
        )

        # Result format: (image, status_text)
        if not result or len(result) < 2:
            print(f"  ❌ Unexpected result format: {result}")
            return None, "Unexpected result format"

        image_data, status = result

        # Extract image file
        if isinstance(image_data, dict) and 'name' in image_data:
            temp_file = Path(image_data['name'])
        elif isinstance(image_data, str):
            temp_file = Path(image_data)
        else:
            print(f"  ❌ Could not extract image from: {image_data}")
            return None, "Could not extract image"

        # Copy to test output directory
        TEST_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = TEST_OUTPUT_DIR / f"zimage_{day}_{timestamp}.png"

        import shutil
        shutil.copy(temp_file, output_file)

        size_kb = output_file.stat().st_size / 1024
        print(f"  ✓ Generated: {output_file.name}")
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


def upscale_with_realesrgan(input_file: Path, scale: float = 2.0) -> tuple[Path, str]:
    """Upscale image using Real-ESRGAN via Dashboard service."""
    try:
        from gradio_client import Client
        from PIL import Image

        print(f"\n📈 Real-ESRGAN Upscaling")
        print(f"  📁 Input: {input_file.name}")
        print(f"  🔗 Connecting to {REALESRGAN_URL}")

        client = Client(REALESRGAN_URL)

        # Load image
        image = Image.open(input_file)

        # Function signature from realesrgan_gradio.py:
        # upscale_image(image, model_name, output_scale, face_enhance, tile_size, denoise_strength)

        print(f"  ⏳ Upscaling {scale}x...")
        result = client.predict(
            image=str(input_file),  # Can pass file path
            model_name="RealESRGAN_x4plus",
            output_scale=scale,
            face_enhance=False,
            tile_size=256,  # Use tiling to save VRAM
            denoise_strength=0.5,
            api_name="/upscale_image"
        )

        # Result format: (image, status_text)
        if not result or len(result) < 2:
            print(f"  ❌ Unexpected result format: {result}")
            return None, "Unexpected result format"

        image_data, status = result

        # Extract upscaled image
        if isinstance(image_data, dict) and 'name' in image_data:
            temp_file = Path(image_data['name'])
        elif isinstance(image_data, str):
            temp_file = Path(image_data)
        else:
            print(f"  ❌ Could not extract image from: {image_data}")
            return None, "Could not extract image"

        # Copy to test output directory with _upscaled suffix
        output_file = input_file.with_stem(f"{input_file.stem}_upscaled")

        import shutil
        shutil.copy(temp_file, output_file)

        size_kb = output_file.stat().st_size / 1024
        print(f"  ✓ Upscaled: {output_file.name}")
        print(f"  📦 Size: {size_kb:.1f} KB")

        return output_file, status

    except ImportError:
        print(f"  ❌ gradio_client not found")
        return None, "gradio_client not installed"

    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None, str(e)


def main():
    parser = argparse.ArgumentParser(
        description="Test character generation with DragonFlux Klein vs Z-Image Base",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test Monday character generation
  %(prog)s --day monday

  # Test with upscaling
  %(prog)s --day monday --upscale

  # Test different day
  %(prog)s --day friday --upscale

Available Days:
  monday, tuesday, wednesday, thursday, friday
        """
    )

    parser.add_argument(
        "--day",
        choices=list(CHARACTER_PROMPTS.keys()),
        default="monday",
        help="Day of the week for character variant"
    )
    parser.add_argument(
        "--upscale",
        action="store_true",
        help="Upscale generated images with Real-ESRGAN"
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=2.0,
        help="Upscale factor (default: 2.0)"
    )

    args = parser.parse_args()

    # Get character prompt for the day
    prompt_data = CHARACTER_PROMPTS[args.day]
    prompt = prompt_data["description"]
    negative = prompt_data["negative"]

    print(f"🎭 Vocab Character Test - {args.day.capitalize()}")
    print(f"=" * 60)
    print(f"\n📋 Character Spec:")
    print(f"  Day: {args.day.capitalize()}")
    print(f"  Frame: {prompt_data['frame']}")
    print(f"  Resolution: 576x1024 (9:16 portrait)")

    # Check services
    print(f"\n🔍 Checking Services...")
    dragonflux_ok = check_service(DRAGONFLUX_URL, "DragonFlux Klein")
    zimage_ok = check_service(ZIMAGE_URL, "Z-Image Base")

    if args.upscale:
        realesrgan_ok = check_service(REALESRGAN_URL, "Real-ESRGAN")
        if not realesrgan_ok:
            print(f"\n⚠️ Real-ESRGAN not running, skipping upscale")
            args.upscale = False

    if not dragonflux_ok and not zimage_ok:
        print(f"\n❌ No image generation services available")
        print(f"\n💡 Start services:")
        print(f"   bash /srv/containers/edq/scripts/start_flux2_klein.sh")
        print(f"   bash /srv/containers/edq/scripts/start_zimage.sh")
        sys.exit(1)

    results = {}

    # Generate with DragonFlux Klein
    if dragonflux_ok:
        flux_file, flux_status = generate_with_dragonflux(prompt, args.day)
        if flux_file:
            results['dragonflux'] = flux_file

            if args.upscale:
                flux_upscaled, _ = upscale_with_realesrgan(flux_file, args.scale)
                if flux_upscaled:
                    results['dragonflux_upscaled'] = flux_upscaled

    # Generate with Z-Image Base
    if zimage_ok:
        zimage_file, zimage_status = generate_with_zimage(prompt, negative, args.day)
        if zimage_file:
            results['zimage'] = zimage_file

            if args.upscale:
                zimage_upscaled, _ = upscale_with_realesrgan(zimage_file, args.scale)
                if zimage_upscaled:
                    results['zimage_upscaled'] = zimage_upscaled

    # Summary
    print(f"\n" + "=" * 60)
    print(f"✓ Test Complete - {args.day.capitalize()}")
    print(f"\n📁 Test Output Directory:")
    print(f"   {TEST_OUTPUT_DIR}")
    print(f"\n🖼️ Generated Files:")

    for name, filepath in results.items():
        print(f"   [{name}] {filepath.name}")

    print(f"\n💡 Compare images to choose best generator for character assets")
    print(f"💡 Final assets will be saved to: {CHARACTER_OUTPUT_DIR}")


if __name__ == "__main__":
    main()
