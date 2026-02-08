#!/usr/bin/env python3
"""
Dragon File Watcher - Automated AI-powered file renaming
Watches Downloads and ai_generated folders, uses Dragonsight 4 (Ollama VLM) to intelligently rename files.
"""

import os
import sys
import time
import base64
import json
import logging
import re
from pathlib import Path
from datetime import datetime
from typing import Optional

import requests
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent

# Configuration
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
DEFAULT_MODEL = "qwen3-vl:8b"

WATCH_DIRS = [
    Path.home() / "Downloads",
    Path.home() / "ai_generated",
]

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tiff', '.heic'}
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv'}

# Patterns to skip (already well-named files)
SKIP_PATTERNS = [
    r'^[a-z_]+_\d{4}-\d{2}-\d{2}',  # Already has descriptive name with date
    r'^screenshot_',                 # Screenshot files
    r'^dragonsight_',                # Dragonsight outputs
    r'^og-preview',                  # Generated assets
]

# Setup logging
LOG_DIR = Path.home() / ".cache" / "dragon-file-watcher"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / f"watcher_{datetime.now().strftime('%Y%m%d')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def should_skip_file(filename: str) -> bool:
    """Check if file should be skipped based on naming patterns."""
    name_lower = filename.lower()

    # Skip if already has a good descriptive name
    for pattern in SKIP_PATTERNS:
        if re.match(pattern, name_lower):
            return True

    # Skip if filename is already long and descriptive (>30 chars)
    base_name = Path(filename).stem
    if len(base_name) > 30:
        return True

    return False


def is_generic_filename(filename: str) -> bool:
    """Check if filename is generic (e.g., IMG_1234.jpg, Screenshot.png)."""
    patterns = [
        r'^IMG_\d+',
        r'^DSC\d+',
        r'^photo_\d+',
        r'^image_\d+',
        r'^screenshot',
        r'^screen\s?shot',
        r'^untitled',
        r'^new\s?image',
        r'^\d{8}_\d{6}',  # Generic timestamp only
    ]

    name_lower = Path(filename).stem.lower()
    return any(re.match(pattern, name_lower) for pattern in patterns)


def sanitize_filename(text: str) -> str:
    """Convert text to safe filename format."""
    # Remove special chars, convert to lowercase, replace spaces with underscores
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '_', text)
    return text[:100]  # Limit length


def file_to_base64(file_path: Path) -> str:
    """Convert image file to base64 string."""
    with open(file_path, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')


def call_ollama(base64_image: str, model: str = DEFAULT_MODEL) -> Optional[str]:
    """Call Ollama API to get filename suggestion."""
    prompt = (
        "Suggest a descriptive filename for this image based on visible content. "
        "Use lowercase, underscores, and be specific. "
        "Only provide the filename without extension or explanation."
    )

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": model,
                "prompt": prompt,
                "images": [base64_image],
                "stream": False
            },
            timeout=60
        )

        if response.status_code != 200:
            logger.error(f"Ollama API error: {response.status_code} - {response.text}")
            return None

        data = response.json()
        suggested_name = data.get('response', '').strip()

        # Clean up the response (sometimes models add extra text)
        # Extract just the filename part
        suggested_name = suggested_name.split('\n')[0].strip()
        suggested_name = suggested_name.replace('.jpg', '').replace('.png', '')

        return sanitize_filename(suggested_name)

    except Exception as e:
        logger.error(f"Ollama API call failed: {e}")
        return None


def rename_file(file_path: Path, suggested_name: str) -> bool:
    """Rename file with AI-suggested name, adding date and preserving extension."""
    try:
        # Get file extension
        ext = file_path.suffix

        # Add date to avoid collisions
        date_str = datetime.now().strftime('%Y-%m-%d')
        new_filename = f"{suggested_name}_{date_str}{ext}"

        # Handle name collisions
        new_path = file_path.parent / new_filename
        counter = 1
        while new_path.exists():
            new_filename = f"{suggested_name}_{date_str}_{counter}{ext}"
            new_path = file_path.parent / new_filename
            counter += 1

        # Perform rename
        file_path.rename(new_path)
        logger.info(f"✓ Renamed: {file_path.name} → {new_filename}")
        return True

    except Exception as e:
        logger.error(f"Failed to rename {file_path}: {e}")
        return False


def process_file(file_path: Path) -> None:
    """Process a single file: analyze with AI and rename."""
    try:
        # Wait a bit to ensure file is fully written
        time.sleep(2)

        if not file_path.exists():
            return

        # Check if we should skip this file
        if should_skip_file(file_path.name):
            logger.debug(f"Skipping (already well-named): {file_path.name}")
            return

        # Only process files with generic names
        if not is_generic_filename(file_path.name):
            logger.debug(f"Skipping (not generic): {file_path.name}")
            return

        logger.info(f"🔍 Processing: {file_path.name}")

        # Convert to base64
        base64_image = file_to_base64(file_path)

        # Get AI suggestion
        suggested_name = call_ollama(base64_image)

        if not suggested_name:
            logger.warning(f"No suggestion received for {file_path.name}")
            return

        # Rename the file
        rename_file(file_path, suggested_name)

    except Exception as e:
        logger.error(f"Error processing {file_path}: {e}")


class ImageFileHandler(FileSystemEventHandler):
    """Handle file system events for image files."""

    def __init__(self):
        super().__init__()
        self.processing_queue = set()

    def on_created(self, event):
        """Handle file creation events."""
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        # Check if it's an image file
        if file_path.suffix.lower() not in IMAGE_EXTENSIONS:
            return

        # Avoid duplicate processing
        if str(file_path) in self.processing_queue:
            return

        self.processing_queue.add(str(file_path))

        try:
            process_file(file_path)
        finally:
            self.processing_queue.discard(str(file_path))


def check_ollama_available() -> bool:
    """Check if Ollama is running and model is available."""
    try:
        # Try to list models
        response = requests.get("http://127.0.0.1:11434/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get('models', [])
            model_names = [m.get('name', '') for m in models]
            if DEFAULT_MODEL in model_names:
                logger.info(f"✓ Ollama running with {DEFAULT_MODEL}")
                return True
            else:
                logger.warning(f"⚠ Ollama running but {DEFAULT_MODEL} not found")
                logger.info(f"Available models: {', '.join(model_names)}")
                return len(model_names) > 0  # Use any available VLM
    except Exception as e:
        logger.error(f"❌ Ollama not available: {e}")
        return False


def main():
    """Main entry point."""
    logger.info("🐉 Dragon File Watcher starting...")

    # Check if Ollama is available
    if not check_ollama_available():
        logger.error("Ollama is not running or no vision models available!")
        logger.error("Please start Ollama and ensure qwen3-vl:8b or llama3.2-vision is installed.")
        sys.exit(1)

    # Verify watch directories exist
    for watch_dir in WATCH_DIRS:
        if not watch_dir.exists():
            logger.warning(f"⚠ Directory does not exist: {watch_dir}")
            continue
        logger.info(f"👁 Watching: {watch_dir}")

    # Create observer
    event_handler = ImageFileHandler()
    observer = Observer()

    # Add watchers for all directories (including subdirectories)
    for watch_dir in WATCH_DIRS:
        if watch_dir.exists():
            observer.schedule(event_handler, str(watch_dir), recursive=True)

    # Start watching
    observer.start()
    logger.info("✓ File watcher started. Press Ctrl+C to stop.")
    logger.info(f"📝 Logs: {LOG_FILE}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("⏹ Stopping file watcher...")
        observer.stop()

    observer.join()
    logger.info("✓ File watcher stopped.")


if __name__ == "__main__":
    main()
