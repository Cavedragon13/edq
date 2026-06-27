#!/usr/bin/env bash
# Download selected Krea 2 LoRA weights into the local Krea runner.
set -euo pipefail

cd /srv/containers/edq
source venv_dragonsuite/bin/activate

python3 - "$@" <<'PY'
import json
import sys
from pathlib import Path

from huggingface_hub import hf_hub_download

LORA_DIR = Path("/srv/containers/edq/krea2/loras")
MANIFEST = LORA_DIR / "manifest.json"


def usage(items):
    print("Usage: bash scripts/download_krea2_loras.sh list|all|NAME [NAME ...]")
    print("")
    print("Official names:")
    for item in items:
        print(f"  {item['id']:15s} {item['repo_id']} / {item['filename']}")


def main():
    LORA_DIR.mkdir(parents=True, exist_ok=True)
    data = json.loads(MANIFEST.read_text())
    items = data.get("official", [])
    by_id = {item["id"]: item for item in items}

    requested = sys.argv[1:]
    if not requested or requested == ["list"]:
        usage(items)
        return 0

    if requested == ["all"]:
        selected = items
    else:
        missing = [name for name in requested if name not in by_id]
        if missing:
            print("Unknown LoRA name(s): " + ", ".join(missing), file=sys.stderr)
            usage(items)
            return 2
        selected = [by_id[name] for name in requested]

    for item in selected:
        target = LORA_DIR / item["filename"]
        if target.exists() and target.stat().st_size > 0:
            print(f"Already present: {target}", flush=True)
            continue
        print(f"Downloading {item['repo_id']}:{item['filename']} -> {target}", flush=True)
        hf_hub_download(
            repo_id=item["repo_id"],
            filename=item["filename"],
            local_dir=str(LORA_DIR),
        )
        print(f"  done ({target.stat().st_size / (1024 * 1024):.1f} MB)", flush=True)

    print("")
    print("LoRAs ready. Refresh Krea 2 Turbo and choose them from the LoRA dropdown.", flush=True)
    return 0


raise SystemExit(main())
PY
