#!/usr/bin/env python3
"""
WanGP2 Model Downloader
Pre-download models to avoid UI download confusion
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import List, Dict

# Recommended models for 16GB VRAM
RECOMMENDED_MODELS = [
    "ltx2_19B.json",           # LTX-2 19B (already downloaded)
    "ovi_1_1.json",            # Wan 2.2 Ovi - fastest (6GB)
    "flux2_klein_4b.json",     # Flux 2 Klein 4B
    "i2v_2_2.json",            # Wan 2.2 Image-to-Video
    "t2v_2_2.json",            # Wan 2.2 Text-to-Video
]

# Optional: Additional interesting models
OPTIONAL_MODELS = [
    "hunyuan_1_5_480_i2v.json",  # HunyuanVideo 1.5
    "flux2_dev.json",            # Flux 2 Dev (image gen)
    "z_image_base.json",         # Z-Image Base (image gen)
    "animate.json",              # Wan2.2-Animate
    "flux_dev_kontext.json",     # Flux Dev Kontext (img2img)
]


def load_model_config(config_path: Path) -> Dict:
    """Load model configuration JSON."""
    with open(config_path) as f:
        return json.load(f)


def download_file(url: str, output_dir: Path) -> bool:
    """Download a file using wget."""
    filename = url.split("/")[-1]
    output_path = output_dir / filename

    if output_path.exists():
        print(f"  ✓ Already downloaded: {filename}")
        return True

    print(f"  📥 Downloading: {filename}")
    print(f"     URL: {url}")

    try:
        result = subprocess.run(
            ["wget", "-c", "-P", str(output_dir), url],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            print(f"  ✅ Downloaded: {filename}")
            return True
        else:
            print(f"  ❌ Failed: {filename}")
            print(f"     Error: {result.stderr}")
            return False
    except Exception as e:
        print(f"  ❌ Error downloading {filename}: {e}")
        return False


def download_model(config_path: Path, ckpts_dir: Path):
    """Download all files for a model configuration."""
    config = load_model_config(config_path)
    model = config.get("model", {})

    model_name = model.get("name", config_path.stem)
    print(f"\n📦 {model_name}")
    print(f"   {model.get('description', 'No description')}")

    # Download main model URLs
    urls = model.get("URLs", [])
    preload_urls = model.get("preload_URLs", [])
    lora_urls = model.get("loras", [])

    all_urls = urls + preload_urls + lora_urls

    if not all_urls:
        print("  ⚠️  No URLs found in configuration")
        return

    success_count = 0
    for url in all_urls:
        if download_file(url, ckpts_dir):
            success_count += 1

    print(f"  📊 Downloaded {success_count}/{len(all_urls)} files")


def main():
    # Paths
    project_dir = Path("/srv/containers/edq/projects/Wan2GP")
    defaults_dir = project_dir / "defaults"
    ckpts_dir = project_dir / "ckpts"

    if not defaults_dir.exists():
        print(f"❌ Defaults directory not found: {defaults_dir}")
        sys.exit(1)

    if not ckpts_dir.exists():
        print(f"Creating checkpoints directory: {ckpts_dir}")
        ckpts_dir.mkdir(parents=True)

    # Parse arguments
    download_all = "--all" in sys.argv
    download_recommended = "--recommended" in sys.argv or len(sys.argv) == 1

    print("🎬 WanGP2 Model Downloader")
    print("=" * 50)
    print(f"Defaults: {defaults_dir}")
    print(f"Checkpoints: {ckpts_dir}")
    print()

    if download_all:
        print("📚 Mode: Download ALL available models")
        model_configs = sorted(defaults_dir.glob("*.json"))
    elif download_recommended:
        print("⭐ Mode: Download RECOMMENDED models (16GB VRAM)")
        model_configs = [defaults_dir / name for name in RECOMMENDED_MODELS]
    else:
        # Custom model list from arguments
        model_names = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
        model_configs = [defaults_dir / (name if name.endswith(".json") else f"{name}.json")
                        for name in model_names]

    # Check for missing configs
    missing = [cfg for cfg in model_configs if not cfg.exists()]
    if missing:
        print("\n⚠️  Warning: Missing configurations:")
        for cfg in missing:
            print(f"  - {cfg.name}")

    model_configs = [cfg for cfg in model_configs if cfg.exists()]

    if not model_configs:
        print("\n❌ No valid model configurations found!")
        print("\nUsage:")
        print("  python wan2gp_download_models.py              # Download recommended")
        print("  python wan2gp_download_models.py --all        # Download ALL models")
        print("  python wan2gp_download_models.py ltx2_19B ovi_1_1  # Download specific models")
        sys.exit(1)

    print(f"\n📋 Will download {len(model_configs)} model(s)")
    print()

    # Download models
    for config_path in model_configs:
        try:
            download_model(config_path, ckpts_dir)
        except Exception as e:
            print(f"\n❌ Error processing {config_path.name}: {e}")

    print("\n✅ Model download complete!")
    print(f"📁 Models saved to: {ckpts_dir}")


if __name__ == "__main__":
    main()
