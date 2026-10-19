#!/bin/bash
# Pre-download every model UniForge3D touches (run once before first launch).
#   xibushu/UniForge3D            ~27GB  UniForge3D checkpoints (local dir, passed to from_pretrained)
#   microsoft/TRELLIS.2-4B                shape/texture decoders + structure flow  (HF cache, pinned rev)
#   microsoft/TRELLIS-image-large         structure decoder + stage-1 DiT base      (HF cache, pinned rev)
#   facebook/dinov3-vitl16-pretrain-lvd1689m   DINOv3 image features (gated: licence accepted on HF account)
#   briaai/RMBG-2.0                       background remover (gated; non-commercial unless licensed)
# Filenames/revisions mirror projects/UniForge3D/uniforge3d/configs/pipeline.json.
set -e
cd /srv/containers/edq
export HF_HOME="${HF_HOME:-/home/edq/.cache/huggingface}"

/srv/containers/edq/venv_uniforge3d/bin/python - << 'PYEOF'
import os
from huggingface_hub import snapshot_download

ROOT = "/srv/containers/edq/models/uniforge3d"
os.makedirs(ROOT, exist_ok=True)

print("UniForge3D checkpoints ->", ROOT, flush=True)
snapshot_download("xibushu/UniForge3D", local_dir=ROOT, allow_patterns=["pipeline.json", "uniforge3d/**/*.pt"])

print("TRELLIS-image-large (structure decoder)", flush=True)
snapshot_download(
    "microsoft/TRELLIS-image-large",
    revision="25e0d31ffbebe4b5a97464dd851910efc3002d96",
    allow_patterns=["ckpts/ss_dec_conv3d_16l8_fp16.json", "ckpts/ss_dec_conv3d_16l8_fp16.safetensors"],
)

print("TRELLIS.2-4B (flow + decoders)", flush=True)
snapshot_download(
    "microsoft/TRELLIS.2-4B",
    revision="af44b45f2e35a493886929c6d786e563ec68364d",
    allow_patterns=[
        "ckpts/ss_flow_img_dit_1_3B_64_bf16.safetensors",
        "ckpts/shape_dec_next_dc_f16c32_fp16.json",
        "ckpts/shape_dec_next_dc_f16c32_fp16.safetensors",
        "ckpts/tex_dec_next_dc_f16c32_fp16.json",
        "ckpts/tex_dec_next_dc_f16c32_fp16.safetensors",
    ],
)

print("DINOv3 ViT-L/16", flush=True)
snapshot_download("facebook/dinov3-vitl16-pretrain-lvd1689m")

print("RMBG-2.0", flush=True)
snapshot_download("briaai/RMBG-2.0")

print("All models ready. Launch with: bash scripts/start_uniforge3d.sh")
PYEOF
