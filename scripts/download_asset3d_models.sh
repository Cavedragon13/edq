#!/bin/bash
# Pre-download all 3D Asset Studio models (Pixal3D + TRELLIS.2, int8) into
# ComfyUI's models/ tree. Run once before first launch (~14.3GB).
# File list = the "Model Links" note in ComfyUI's official template
# 3d_pixal3d_trellis2_image_to_model; repos verified on HF 2026-09-24.
set -e
cd /srv/containers/edq
COMFY_MODELS=/srv/containers/edq/projects/ComfyUI/models

# BiRefNet is byte-identical (sha256 9ab37426…a154) to TripoSplat's copy — link it, don't duplicate.
mkdir -p "$COMFY_MODELS/background_removal"
ln -sfn /srv/containers/edq/models/triposplat/background_removal/birefnet.safetensors \
    "$COMFY_MODELS/background_removal/birefnet.safetensors"

venv_comfyui/bin/python3 - <<'PYEOF'
from huggingface_hub import snapshot_download

MODELS = "/srv/containers/edq/projects/ComfyUI/models"
FILES = {
    "Comfy-Org/Pixal3D": [
        "diffusion_models/pixal3d_int8_convrot.safetensors",
        "clip_vision/dino_v3_L_naf_fp32.safetensors",
        "vae/trellis_2_shape_vae_bf16.safetensors",
        "vae/trellis_2_texture_vae_bf16.safetensors",
    ],
    "Comfy-Org/TRELLIS.2": ["diffusion_models/trellis_2_int8_convrot.safetensors"],
    "Comfy-Org/MoGe": ["geometry_estimation/moge_2_vitl_normal_fp16.safetensors"],
}
for repo, files in FILES.items():
    print(f"Downloading {repo}: {', '.join(files)}", flush=True)
    snapshot_download(repo_id=repo, local_dir=MODELS, allow_patterns=files)
print("All 3D Asset Studio models ready. Launch with: bash scripts/start_asset3d.sh")
PYEOF
