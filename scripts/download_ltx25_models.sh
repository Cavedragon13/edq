#!/bin/bash
# Pre-download all LTX-2.5 (Diffusers) models — run once before first launch.
#
# Part 1: distilled transformer GGUF (ungated, ~12.9GB)
# Part 2: official Lightricks/LTX-2.5-Diffusers components (GATED — accept the
#         license at https://huggingface.co/Lightricks/LTX-2.5-Diffusers first;
#         it is gated separately from the base LTX-2.5 repo).
#
# Skips transformer/ + transformer_full/ (BF16, 38GB each) — the GGUF replaces them.
set -e
cd /srv/containers/edq
source venv_ltx25/bin/activate

GGUF_DIR=/srv/containers/edq/models/ltx25
GGUF_FILE="$GGUF_DIR/LTX-2.5-Distilled-Q3_K_M.gguf"

mkdir -p "$GGUF_DIR"
if [ -f "$GGUF_FILE" ] && [ ! -f "$GGUF_FILE.aria2" ]; then
    echo "GGUF transformer already present: $GGUF_FILE"
else
    echo "Downloading distilled Q3_K_M GGUF (~12.9GB)..."
    aria2c -x 8 -s 8 -c --console-log-level=warn -d "$GGUF_DIR" \
        -o LTX-2.5-Distilled-Q3_K_M.gguf \
        "https://huggingface.co/Abiray/LTX-2.5-Distilled-GGUF/resolve/main/LTX-2.5-Distilled-Q3_K_M.gguf"
fi

python3 << 'PYEOF'
import os
from huggingface_hub import snapshot_download
from huggingface_hub.errors import GatedRepoError, HfHubHTTPError

local_dir = "/srv/containers/edq/models/ltx25/LTX-2.5-Diffusers"
os.makedirs(local_dir, exist_ok=True)

# Everything except the BF16 transformers and the redundant combined connectors file.
allow = [
    "model_index.json",
    "modular_model_index.json",
    "scheduler/*",
    "tokenizer/*",
    "text_encoder/*",
    "vae/*",
    "audio_vae/*",
    "vocoder/*",
    "diffusion_decoder/*",
    "latent_upsampler/*",
    "duration_head/*",
    "transformer/config.json",
    "connectors/config.json",
    "connectors/diffusion_pytorch_model-*-of-00002.safetensors",
    "connectors/diffusion_pytorch_model.safetensors.index.json",
]

try:
    snapshot_download(
        repo_id="Lightricks/LTX-2.5-Diffusers",
        local_dir=local_dir,
        allow_patterns=allow,
    )
    print("All gated components downloaded to", local_dir)
except (GatedRepoError, HfHubHTTPError) as e:
    if "403" in str(e) or "restricted" in str(e).lower() or "gated" in str(e).lower():
        print("BLOCKED: accept the license at "
              "https://huggingface.co/Lightricks/LTX-2.5-Diffusers then re-run this script.")
        raise SystemExit(1)
    raise
print("All models ready. Launch with: bash scripts/start_ltx25.sh")
PYEOF
