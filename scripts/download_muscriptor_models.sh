#!/bin/bash
# Pre-download MuScriptor model weights (run once before first launch)
#
# ⚠️  GATED MODELS: MuScriptor repos are gated (auto-approval). Before this
#     works, accept the terms once while logged in as Cavedragon at:
#       https://huggingface.co/MuScriptor/muscriptor-large
#     Then re-run this script. The local HF token is already configured.
set -e
cd /srv/containers/edq
source venv_muscriptor/bin/activate

python3 << 'PYEOF'
from huggingface_hub import hf_hub_download
from huggingface_hub.errors import GatedRepoError, HfHubHTTPError

REPO = "MuScriptor/muscriptor-large"   # 1.4B — best accuracy, wants the GPU
try:
    for filename in ("config.json", "model.safetensors"):
        print(f"Downloading {REPO}/{filename}")
        hf_hub_download(repo_id=REPO, filename=filename)
    print("All models ready. Launch with: bash scripts/start_muscriptor.sh")
except (GatedRepoError, HfHubHTTPError) as e:
    print(f"\n❌ Download failed: {e}")
    print("\nMuScriptor is gated (auto-approval). Accept the terms once at:")
    print(f"  https://huggingface.co/{REPO}")
    print("then re-run this script.")
    raise SystemExit(1)
PYEOF
