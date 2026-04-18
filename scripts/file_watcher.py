#!/usr/bin/env python3
"""Dragon File Watcher — AI-powered file renaming using Gemma4 via Ollama.
Scans Downloads (top-level only) and ai_generated (all subfolders) every 3 hours.
"""

import os
import sys
import json
import base64
import logging
import re
import time
from collections import defaultdict
from pathlib import Path
from datetime import datetime
from typing import Optional

import requests

OLLAMA_URL = "http://127.0.0.1:11434"
MODEL = "gemma4:e4b"
SCAN_INTERVAL = 3 * 60 * 60  # seconds

DOWNLOADS_DIR = Path.home() / "Downloads"
AI_GENERATED_DIR = Path.home() / "ai_generated"

CACHE_DIR = Path.home() / ".cache" / "dragon-file-watcher"
STATE_FILE = CACHE_DIR / "processed.json"
LOG_FILE = CACHE_DIR / f"watcher_{datetime.now().strftime('%Y%m')}.log"

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tiff', '.heic', '.avif'}
AUDIO_EXTS = {'.wav', '.mp3', '.flac', '.ogg', '.m4a', '.aac', '.opus'}
VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv'}
ALL_EXTS = IMAGE_EXTS | AUDIO_EXTS | VIDEO_EXTS

# Files already named by Dragonsuite services — skip
SERVICE_PREFIX_RE = re.compile(
    r'^(voxcpm2|dragonsight|flux2|ltx|ace_step|fish_speech|qwen_tts|omnivoice|tada|'
    r'dragonart|heartmula|realesrgan|sam2_|liveportrait|hunyuan|zimage|streetview|'
    r'rembg|audio_ws|foundation\d)[\s_-]?\d',
    re.IGNORECASE
)

# Generic patterns that are worth renaming
GENERIC_RE = re.compile(
    r'^(img|dsc|photo|image|screenshot|screen_shot|untitled|new_image|'
    r'file|audio|video|recording|clip|output|temp|tmp|download|attachment|'
    r'voice|memo|capture|scan)[\s_\-]?\d*$'
    r'|^[a-f0-9]{8}-[a-f0-9]{4}'   # UUID-like
    r'|^\d{8}[\s_-]?\d{6}$'        # Pure timestamp
    r'|^[a-z]{1,6}\d+$',           # Short word + digits (vid001, img002)
    re.IGNORECASE
)


def setup_logging():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler(sys.stdout),
        ]
    )


logger = logging.getLogger(__name__)


def load_state() -> set:
    if STATE_FILE.exists():
        try:
            return set(json.loads(STATE_FILE.read_text()))
        except Exception:
            return set()
    return set()


def save_state(processed: set):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(sorted(processed), indent=2))


def needs_rename(file_path: Path) -> bool:
    stem = file_path.stem
    if SERVICE_PREFIX_RE.match(stem):
        return False
    if len(stem) > 40:  # already descriptive
        return False
    return bool(GENERIC_RE.match(stem))


def sanitize(text: str) -> str:
    text = text.lower().strip("'\"` \t\n")
    # Strip common model verbosity
    for phrase in ("filename:", "name:", "suggestion:", "here", "is the"):
        text = text.replace(phrase, "")
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s\-]+', '_', text)
    text = text.strip('_')
    return text[:50] or "file"


def get_suggestion(file_path: Path) -> Optional[str]:
    try:
        if file_path.suffix.lower() in IMAGE_EXTS:
            b64 = base64.b64encode(file_path.read_bytes()).decode()
            payload = {
                "model": MODEL,
                "prompt": (
                    "Give a short descriptive filename for this image: 2-4 words, "
                    "lowercase, underscores. Reply with ONLY the filename, no extension, no extra text."
                ),
                "images": [b64],
                "stream": False,
            }
            timeout = 90
        else:
            # Audio/video: use text context only
            ext = file_path.suffix.lstrip('.').upper()
            payload = {
                "model": MODEL,
                "prompt": (
                    f"Suggest a short descriptive filename (2-4 words, lowercase underscores) for a "
                    f"{ext} file named '{file_path.stem}' located in folder '{file_path.parent.name}'. "
                    "Reply with ONLY the filename, no extension, no extra text."
                ),
                "stream": False,
            }
            timeout = 30

        resp = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=timeout)
        resp.raise_for_status()
        raw = resp.json().get("response", "").strip().split("\n")[0]
        return sanitize(raw)

    except Exception as e:
        logger.warning(f"Ollama call failed for {file_path.name}: {e}")
        return None


def rename_file(file_path: Path, new_stem: str) -> Optional[Path]:
    new_path = file_path.parent / f"{new_stem}{file_path.suffix.lower()}"
    counter = 1
    while new_path.exists() and new_path.resolve() != file_path.resolve():
        new_path = file_path.parent / f"{new_stem}_{counter:02d}{file_path.suffix.lower()}"
        counter += 1
    if new_path.resolve() == file_path.resolve():
        return file_path
    try:
        file_path.rename(new_path)
        logger.info(f"  ✓ {file_path.name} → {new_path.name}")
        return new_path
    except Exception as e:
        logger.error(f"  ✗ Rename failed {file_path}: {e}")
        return None


def collect_files(processed: set) -> list:
    files = []

    # Downloads: top-level files only, no recursion
    if DOWNLOADS_DIR.exists():
        for f in sorted(DOWNLOADS_DIR.iterdir()):
            if f.is_file() and f.suffix.lower() in ALL_EXTS and str(f) not in processed:
                if needs_rename(f):
                    files.append(f)

    # ai_generated: all subfolders recursively
    if AI_GENERATED_DIR.exists():
        for f in sorted(AI_GENERATED_DIR.rglob("*")):
            if f.is_file() and f.suffix.lower() in ALL_EXTS and str(f) not in processed:
                if needs_rename(f):
                    files.append(f)

    return files


def process_batch(files: list, processed: set):
    logger.info(f"🔍 {len(files)} file(s) to rename...")

    # Get suggestions
    suggestions = {}
    for f in files:
        suggestion = get_suggestion(f)
        if suggestion:
            suggestions[f] = suggestion
        else:
            processed.add(str(f))  # mark seen even without suggestion

    # Group by (parent_dir, base_suggestion) for sequential naming
    groups = defaultdict(list)
    for f, s in suggestions.items():
        groups[(f.parent, s)].append(f)

    for (parent, base_name), group_files in groups.items():
        # Sort by modification time to preserve logical order
        group_files.sort(key=lambda p: p.stat().st_mtime)
        use_seq = len(group_files) > 1
        for i, f in enumerate(group_files, 1):
            stem = f"{base_name}_{i:02d}" if use_seq else base_name
            result = rename_file(f, stem)
            processed.add(str(result) if result else str(f))


def scan_once(processed: set):
    files = collect_files(processed)
    if not files:
        logger.info("✓ Scan complete — nothing to rename")
        return
    process_batch(files, processed)
    save_state(processed)
    logger.info(f"✓ Scan complete — total processed: {len(processed)}")


def check_ollama() -> bool:
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        models = [m["name"] for m in resp.json().get("models", [])]
        if MODEL not in models:
            logger.error(f"❌ Model {MODEL} not in Ollama. Available: {', '.join(models)}")
            return False
        logger.info(f"✓ Ollama ready — {MODEL}")
        return True
    except Exception as e:
        logger.error(f"❌ Ollama unavailable: {e}")
        return False


def main():
    setup_logging()
    logger.info("🐉 Dragon File Watcher starting")
    logger.info(f"  Downloads:    {DOWNLOADS_DIR}  (top-level only)")
    logger.info(f"  AI Generated: {AI_GENERATED_DIR}  (recursive)")
    logger.info(f"  Model:        {MODEL}")
    logger.info(f"  Interval:     every {SCAN_INTERVAL // 3600}h")

    if not check_ollama():
        sys.exit(1)

    processed = load_state()
    logger.info(f"  State:        {len(processed)} files already processed")

    while True:
        logger.info(f"⏰ Scan at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        try:
            scan_once(processed)
        except Exception as e:
            logger.error(f"Scan error: {e}", exc_info=True)

        next_run = datetime.fromtimestamp(time.time() + SCAN_INTERVAL)
        logger.info(f"💤 Next scan at {next_run.strftime('%H:%M')}")
        time.sleep(SCAN_INTERVAL)


if __name__ == "__main__":
    main()
