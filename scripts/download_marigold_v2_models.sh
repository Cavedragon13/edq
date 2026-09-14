#!/bin/bash
# Pre-download Marigold V2 (depth / normals / albedo) files for ComfyUI.
# Run once before first launch — never let a workflow pull these at runtime.
#
# Marigold V2 is a LoRA over Qwen-Image-Edit-2509 (20B DiT). The official code
# needs ~17 GB at 1024², so on this 16 GB card the only workable backbone is a
# GGUF quant loaded through ComfyUI-GGUF (Q4_K_S, 12.2 GB). The text encoder is
# NOT needed: Marigold ships precomputed prompt embeddings per modality.
#
# The ComfyUI-Marigold-v2 node pack (custom_nodes/) expects the ORIGINAL Huawei
# checkpoint format (trainables.safetensors = LoRA + fine-tuned VAE decoder),
# the plain Qwen-Image VAE, and the embeddings under models/marigold-v2/.
#
# Layout (ComfyUI folders):
#   models/unet/         Qwen-Image-Edit-2509-Q4_K_S.gguf                    (QuantStack)
#   models/vae/          qwen_image_vae.safetensors                          (Comfy-Org repack)
#   models/loras/        marigold-v2-{depth-Log-stage2,normals,albedo}.safetensors (huawei-bayerlab)
#   models/marigold-v2/Marigold-V2/qwen_text_embeddings/*.pt              (huawei-bayerlab)
set -e
cd /srv/containers/edq
COMFY_MODELS="/srv/containers/edq/projects/ComfyUI/models"
PY="/srv/containers/edq/venv_comfyui/bin/python"
"$PY" -c "import huggingface_hub" 2>/dev/null || PY="/srv/containers/edq/venv_dragonsuite/bin/python"

COMFY_MODELS="$COMFY_MODELS" "$PY" - <<'PYEOF'
import os
from huggingface_hub import hf_hub_download

root = os.environ["COMFY_MODELS"]
MG = "huawei-bayerlab/marigold-v2-0"
EMB = "marigold-v2/Marigold-V2/qwen_text_embeddings"
FILES = [
    # (repo, file in repo, ComfyUI subfolder, destination basename)
    ("QuantStack/Qwen-Image-Edit-2509-GGUF", "Qwen-Image-Edit-2509-Q4_K_S.gguf", "unet", None),
    ("Comfy-Org/Qwen-Image_ComfyUI", "split_files/vae/qwen_image_vae.safetensors", "vae", None),
    (MG, "depth/Log-stage2/trainables.safetensors", "loras", "marigold-v2-depth-Log-stage2.safetensors"),
    (MG, "normals/trainables.safetensors", "loras", "marigold-v2-normals.safetensors"),
    (MG, "albedo/trainables.safetensors", "loras", "marigold-v2-albedo.safetensors"),
    (MG, "qwen_text_embeddings/qwen_edit_2509_qwen_depth_realimg512_prompt_embeds.pt", EMB, None),
    (MG, "qwen_text_embeddings/qwen_edit_2509_qwen_depth_realimg512_prompt_mask.pt", EMB, None),
    (MG, "qwen_text_embeddings/qwen_edit_2509_qwen_normals_dummy512_prompt_embeds.pt", EMB, None),
    (MG, "qwen_text_embeddings/qwen_edit_2509_qwen_normals_dummy512_prompt_mask.pt", EMB, None),
    (MG, "qwen_text_embeddings/qwen_edit_2509_qwen_albedo_rgb_dummy512_prompt_embeds.pt", EMB, None),
    (MG, "qwen_text_embeddings/qwen_edit_2509_qwen_albedo_rgb_dummy512_prompt_mask.pt", EMB, None),
]
for repo, filename, sub, rename in FILES:
    dest_dir = os.path.join(root, sub)
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, rename or os.path.basename(filename))
    if os.path.exists(dest):
        print(f"  present  {dest}")
        continue
    print(f"Downloading {repo}/{filename} -> {dest}")
    got = hf_hub_download(repo_id=repo, filename=filename, local_dir=dest_dir)
    if os.path.abspath(got) != os.path.abspath(dest):
        os.replace(got, dest)   # flatten the repo subfolder / apply the rename
    print("  done")
print("All Marigold V2 files ready.")
PYEOF
