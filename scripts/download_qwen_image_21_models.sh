#!/bin/bash
# Pre-download Qwen-Image 2.1 Studio models (run once before first launch; resumable).
#   models/qwen-image-21/Qwen-Image-2.1        full official repo (~33GB)
#   models/qwen-image-21/Qwen-Image-2.1-Turbo  official 8-step checkpoint, transformer + configs
#                                              only (~14GB); its text encoder is byte-identical
#                                              to the base one, so text_encoder/ is a symlink.
# License: Qwen Research License (non-commercial). Repo IDs verified on huggingface.co 2026-10-25.
# Then run scripts/quantize_qwen_image_21.py once to build the NF4 copies the app loads.
set -e
cd /srv/containers/edq
ROOT=/srv/containers/edq/models/qwen-image-21
mkdir -p "$ROOT"
PY="${QI21_PY:-/srv/containers/edq/venv_qwen_image_21/bin/python}"
"$PY" - <<'PYEOF'
from huggingface_hub import snapshot_download
ROOT = "/srv/containers/edq/models/qwen-image-21"
print("Downloading Qwen/Qwen-Image-2.1 ...", flush=True)
snapshot_download("Qwen/Qwen-Image-2.1", local_dir=f"{ROOT}/Qwen-Image-2.1",
                  ignore_patterns=["assets/*"], max_workers=4)
print("Downloading Qwen/Qwen-Image-2.1-Turbo (transformer + configs) ...", flush=True)
snapshot_download("Qwen/Qwen-Image-2.1-Turbo", local_dir=f"{ROOT}/Qwen-Image-2.1-Turbo",
                  ignore_patterns=["assets/*", "text_encoder/*"], max_workers=4)
print("downloads done", flush=True)
PYEOF
TE="$ROOT/Qwen-Image-2.1-Turbo/text_encoder"
if [ ! -e "$TE" ]; then
    ln -s "$ROOT/Qwen-Image-2.1/text_encoder" "$TE"
fi
du -sh "$ROOT"/* || true
echo "All models ready. Next: venv_qwen_image_21/bin/python scripts/quantize_qwen_image_21.py"
