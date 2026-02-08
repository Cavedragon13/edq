#!/usr/bin/env python3
"""
Dragonsuite Icon Batch Generator
Creates cohesive retro-themed thumbnails for all services
Uses local Z-Image on port 8011
"""

from gradio_client import Client
import json
import time
from pathlib import Path

# Dragonsuite theme - Crimson & Bronze (unique, sophisticated)
THEME = {
    "style": "pixel art icon, 8-bit retro game sprite style, simple geometric shapes, clean design, square composition centered",
    "colors": "crimson red and bronze gold gradient background, metallic sheen, warm rich colors",
    "aesthetic": "vintage 1980s gaming aesthetic, blocky retro design, solid color background, steampunk tech vibes",
    "negative": "blurry, complex, detailed background, realistic, photograph, 3d render, text, letters, purple, blue"
}

# Service icon prompts (themed for cohesion)
ICON_PROMPTS = {
    # Games
    "mule-game": {
        "prompt": "pixel art robot mule character, purple blue metallic, cute mechanical quadruped, glowing yellow eyes, 8-bit game sprite",
        "category": "game"
    },

    # Image / Vision
    "dragonsight4": {
        "prompt": "pixel art dragon eye with circuit patterns, purple blue, AI vision sensor, glowing iris, tech aesthetic",
        "category": "image"
    },
    "dragonflux-klein": {
        "prompt": "pixel art energy flux swirl, purple pink gradient, magic sparkles, FLUX symbol, artistic waves",
        "category": "image"
    },
    "zimage-base": {
        "prompt": "pixel art letter Z with image frame, orange yellow, creative art symbol, bold typography icon",
        "category": "image"
    },
    "realesrgan": {
        "prompt": "pixel art upward arrow with sparkles, green blue, resolution enhancement symbol, shimmering pixels",
        "category": "image"
    },
    "dragonart-studio": {
        "prompt": "pixel art paint palette with dragon scales, rainbow colors, artistic tools, creative design",
        "category": "image"
    },

    # Video
    "wan2gp": {
        "prompt": "pixel art film reel spinning, purple blue, video generation symbol, movie camera icon, retro cinema",
        "category": "video"
    },
    "liveportrait": {
        "prompt": "pixel art animated face profile, pink purple, portrait animation symbol, expression change frames",
        "category": "video"
    },

    # 3D
    "hunyuan3d": {
        "prompt": "pixel art rotating 3D cube wireframe, cyan magenta, geometric transformation, isometric view",
        "category": "3d"
    },

    # Audio / TTS / Music
    "qwen3-tts": {
        "prompt": "pixel art speech bubble with sound waves, blue green, TTS voice symbol, audio waveform",
        "category": "audio"
    },
    "qwen3-audiobook": {
        "prompt": "pixel art open book with headphones, brown orange, audiobook symbol, reading listening icon",
        "category": "audio"
    },
    "fish-speech": {
        "prompt": "pixel art cute fish with sound waves, orange blue, TTS icon, swimming musical fish, bubbles",
        "category": "audio"
    },
    "heartmula": {
        "prompt": "pixel art heart shaped musical note, red pink, music generation symbol, love song icon",
        "category": "audio"
    },

    # Segmentation
    "sam2": {
        "prompt": "pixel art segmentation mask cutting tool, green blue, AI scissors icon, selection overlay",
        "category": "segmentation"
    },
    "rembg": {
        "prompt": "pixel art background eraser tool, pink purple, transparency symbol, layer removal icon",
        "category": "segmentation"
    },
    "qwen-image-layered": {
        "prompt": "pixel art stacked transparent layers, rainbow gradient, RGBA layer icon, decomposition symbol",
        "category": "segmentation"
    }
}

# Category accent colors (Crimson & Bronze base + unique accents)
CATEGORY_COLORS = {
    "game": "crimson red bronze gold amber",           # Warm metallics
    "image": "crimson orange bronze copper",           # Fire tones
    "video": "crimson magenta bronze rose gold",       # Rich reds
    "3d": "bronze gold copper metallic silver",        # Pure metallics
    "audio": "crimson burgundy bronze amber",          # Deep reds
    "segmentation": "bronze emerald crimson teal"      # Bronze + cool accent
}

def generate_icon(client, service_id, config, output_dir):
    """Generate a single icon"""
    print(f"🎨 Generating: {service_id}...")

    # Build full prompt
    base_prompt = config["prompt"]
    category = config.get("category", "image")
    category_colors = CATEGORY_COLORS.get(category, "purple blue")

    full_prompt = f"{base_prompt}, {THEME['style']}, {category_colors} colors, {THEME['aesthetic']}"

    try:
        # Z-Image Base parameters (matches zimage_base_gradio.py)
        result = client.predict(
            full_prompt,              # prompt_input
            THEME['negative'],        # negative_prompt
            "1:1 (1024x1024)",       # aspect_ratio
            1024,                     # width_input
            1024,                     # height_input
            7.5,                      # guidance_scale
            30,                       # num_steps
            -1,                       # seed_input (-1 for random)
            "None",                   # lora_dropdown
            1.0,                      # lora_scale
            api_name="/generate_image"  # Explicit API name
        )

        # Result is tuple: (image, status_message)
        # image is either PIL Image or path string
        if isinstance(result, tuple):
            image_result = result[0]
        else:
            image_result = result

        output_path = output_dir / f"{service_id}.png"

        # Handle PIL Image or path
        if hasattr(image_result, 'save'):
            # It's a PIL Image
            image_result.save(output_path)
        else:
            # It's a file path
            import shutil
            shutil.copy2(image_result, output_path)

        print(f"✅ Saved: {output_path}")
        return True

    except Exception as e:
        print(f"❌ Failed: {service_id} - {e}")
        return False

def main():
    print("🚀 Dragonsuite Icon Batch Generator")
    print("=" * 50)

    # Connect to local Z-Image
    print("📡 Connecting to Z-Image (http://127.0.0.1:8011)...")
    try:
        client = Client("http://127.0.0.1:8011/")
        print("✅ Connected!")
    except Exception as e:
        print(f"❌ Failed to connect to Z-Image: {e}")
        print("Make sure Z-Image is running on port 8011")
        return

    # Output directory
    output_dir = Path("/srv/containers/edq/media/thumbnails")
    output_dir.mkdir(exist_ok=True)

    print(f"\n📁 Output: {output_dir}\n")

    # Ask which icons to generate
    print("Available services:")
    for i, service_id in enumerate(ICON_PROMPTS.keys(), 1):
        category = ICON_PROMPTS[service_id].get("category", "?")
        print(f"  {i:2d}. {service_id:20s} [{category}]")

    print("\nOptions:")
    print("  1. Press Enter to generate ALL icons")
    print("  2. Type service IDs separated by spaces (e.g., 'mule-game fish-speech sam2')")
    print("  3. Type 'category:audio' to generate all audio icons")

    choice = input("\nYour choice: ").strip()

    # Determine which icons to generate
    if not choice:
        # Generate all
        to_generate = list(ICON_PROMPTS.keys())
    elif choice.startswith("category:"):
        # Filter by category
        cat = choice.split(":")[1]
        to_generate = [sid for sid, cfg in ICON_PROMPTS.items() if cfg.get("category") == cat]
    else:
        # Specific services
        to_generate = choice.split()

    print(f"\n🎨 Generating {len(to_generate)} icons...\n")

    # Generate icons
    success_count = 0
    for service_id in to_generate:
        if service_id not in ICON_PROMPTS:
            print(f"⚠️  Unknown service: {service_id}, skipping...")
            continue

        config = ICON_PROMPTS[service_id]
        if generate_icon(client, service_id, config, output_dir):
            success_count += 1

        # Rate limit: wait between generations
        time.sleep(2)

    print(f"\n{'='*50}")
    print(f"✅ Generated {success_count}/{len(to_generate)} icons")
    print(f"📁 Location: {output_dir}")
    print("\n🔧 Next steps:")
    print("  1. Review the generated icons")
    print("  2. Update dragonsuite.json with thumbnail paths")
    print("  3. Refresh the dashboard (Ctrl+Shift+R)")

if __name__ == "__main__":
    main()
