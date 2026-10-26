#!/usr/bin/env python3
"""Add (or update) the qwen-image-21 entry in config/dragonsuite.json. Backs up first."""
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

CFG = Path("/srv/containers/edq/config/dragonsuite.json")
ENTRY = {
    "id": "qwen-image-21",
    "name": "Qwen-Image 2.1 Studio",
    "description": "Qwen-Image 2.1 + Turbo: text-to-image, multi-reference editing and native transparent PNGs (non-commercial license)",
    "category": "image",
    "port": 8076,
    "path": "/",
    "icon": "&#127912;",
    "launch_command": "cd /srv/containers/edq && bash scripts/start_qwen_image_21.sh",
    "project_path": None,
    "output_dir": "/home/edq/ai_generated/qwen-image-21",
    "features": ["Turbo 8-step + Base 40-step", "Multi-reference editing", "Transparent RGBA PNG",
                 "2K aspect presets", "NF4 on 16GB"],
    "stop_command": "pkill -f '[q]wen_image_21_gradio.py' || true",
    "vram_gb": 9,
}

dry = "--dry-run" in sys.argv
cfg = json.loads(CFG.read_text())
ids = [s.get("id") for s in cfg["services"]]
clash = [s["id"] for s in cfg["services"] if s.get("port") == ENTRY["port"] and s.get("id") != ENTRY["id"]]
if clash:
    sys.exit(f"port {ENTRY['port']} already used by {clash}")
if ENTRY["id"] in ids:
    cfg["services"][ids.index(ENTRY["id"])] = ENTRY
    action = "updated"
else:
    cfg["services"].append(ENTRY)
    action = "added"
print(action, json.dumps(ENTRY, indent=1))
if not dry:
    bak = CFG.with_name(f"dragonsuite.json.bak-{datetime.now():%Y%m%d-%H%M%S}")
    shutil.copy2(CFG, bak)
    tmp = CFG.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")
    json.loads(tmp.read_text())
    tmp.replace(CFG)
    print("backup:", bak)
