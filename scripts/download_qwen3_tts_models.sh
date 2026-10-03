#!/bin/bash
# Pre-fetch all Qwen3-TTS model weights so first launch never downloads.
# app_local.py loads one of three repos on demand by model_type (see get_model()):
#   CustomVoice, Base, VoiceDesign.
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh
activate_venv venv_qwen3_tts

python3 - <<'PYEOF'
from huggingface_hub import snapshot_download

for repo in [
    "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
    "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
    "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
]:
    print(f"Downloading {repo}...")
    snapshot_download(repo_id=repo)
    print(f"  done: {repo}")
PYEOF

echo "✅ Qwen3-TTS models ready."
