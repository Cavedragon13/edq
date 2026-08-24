#!/bin/bash
# Pre-download SenseNova-U1.5-8B-MoT config/tokenizer + community Q8 GGUF weights
# (run once before first launch)
set -e
cd /srv/containers/edq

venv_sensenova/bin/python3 << 'PYEOF'
import os
from huggingface_hub import snapshot_download, hf_hub_download

CONFIG_DIR = "/srv/containers/edq/models/sensenova-u1.5"
GGUF_DIR = "/srv/containers/edq/models/sensenova-u1.5/gguf"

os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(GGUF_DIR, exist_ok=True)

print("Downloading config/tokenizer from sensenova/SenseNova-U1.5-8B-MoT (safetensors excluded — GGUF override used instead)")
snapshot_download(
    repo_id="sensenova/SenseNova-U1.5-8B-MoT",
    local_dir=CONFIG_DIR,
    ignore_patterns=["*.safetensors", "*.md"],
)
print("  done")

print("Downloading community Q8 GGUF from smthem/SenseNova-U1-8B-MoT-Merger-gguf (official SenseNova ComfyUI docs reference this file)")
hf_hub_download(
    repo_id="smthem/SenseNova-U1-8B-MoT-Merger-gguf",
    filename="SenseNova-U1.5-8B-MoT-Preview-Q8.gguf",
    local_dir=GGUF_DIR,
)
print("  done")

print("All SenseNova-U1.5 assets ready. Launch with: bash scripts/start_sensenova.sh")
PYEOF
