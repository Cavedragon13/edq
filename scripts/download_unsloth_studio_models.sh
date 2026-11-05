#!/bin/bash
# Unsloth Studio — pre-cache the one model it downloads on its own (helper GGUF
# for dataset-assist auto-captioning, unsloth/gemma-4-E2B-it-GGUF). Everything
# else (the model you actually fine-tune) is chosen and downloaded by the user
# from inside the UI, so there is nothing else to pre-fetch here.
set -e
cd /srv/containers/edq

VENV_PY="venv_unsloth_studio/bin/python3"

"$VENV_PY" scripts/download_unsloth_studio_models.py
