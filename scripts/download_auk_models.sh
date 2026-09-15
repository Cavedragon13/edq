#!/bin/bash
# Pre-download AuK models (run once before first launch). Never let the first
# launch pull these silently.
#
# Layout matches the upstream README's expected ckpts/ tree:
#   models/auk/AuK/             base model  (6.1 GB DiT + VAE)
#   models/auk/AuK-Flash/       4-step distilled variant
#   models/auk/Qwen2.5-Omni-3B/ MLLM encoder (loaded separately at runtime)
#
# Also fetches iic/SenseVoiceSmall (~936 MB), the Prompt Enhancer's CPU-side ASR
# fallback for uploaded/reference audio when no Tencent Cloud ASR credentials
# are set (see start_auk.sh's LLM_* vars). Found 2026-09-14 the hard way: it
# auto-downloads via FunASR/ModelScope — a completely separate hub from
# Hugging Face — the first time a PE-enabled request includes audio, silently
# blocking that request for minutes.
#
# 2026-09-14: this network drops mid-transfer on large files (ChunkedEncodingError:
# "Connection broken"). huggingface_hub does NOT auto-retry that — it just raises —
# but it DOES resume from the partial .incomplete blob on the next call. So retry
# each phase a bounded number of times; each retry only re-fetches the bytes
# actually lost, not the whole file.
set -e
cd /srv/containers/edq
PY="/srv/containers/edq/venv_auk/bin/python"
[ -x "$PY" ] && "$PY" -c "import huggingface_hub" 2>/dev/null || PY="/srv/containers/edq/venv_dragonsuite/bin/python"

ATTEMPTS="${AUK_DOWNLOAD_ATTEMPTS:-15}"

hf_ok=0
for i in $(seq 1 "$ATTEMPTS"); do
    echo "--- attempt $i/$ATTEMPTS (AuK / AuK-Flash / Qwen encoder) ---"
    if "$PY" - <<'PYEOF'
import os
from huggingface_hub import snapshot_download

MODELS = [
    ("tencent/AuK",          "/srv/containers/edq/models/auk/AuK"),
    ("tencent/AuK-Flash",    "/srv/containers/edq/models/auk/AuK-Flash"),
    ("Qwen/Qwen2.5-Omni-3B", "/srv/containers/edq/models/auk/Qwen2.5-Omni-3B"),
]
for repo_id, local_dir in MODELS:
    os.makedirs(local_dir, exist_ok=True)
    print(f"Downloading {repo_id} -> {local_dir}")
    snapshot_download(repo_id=repo_id, local_dir=local_dir,
                      ignore_patterns=["assets/*", "*.png", "*.md", ".gitattributes"])
    print("  done")
print("AuK / AuK-Flash / Qwen encoder ready.")
PYEOF
    then
        hf_ok=1
        break
    fi
    echo "  attempt $i failed (likely a dropped connection) — retrying, resuming from partial bytes"
    sleep 5
done
if [ "$hf_ok" != "1" ]; then
    echo "❌ AuK model download did not complete after $ATTEMPTS attempts — check network"
    exit 1
fi

ASR_PY="/srv/containers/edq/venv_auk/bin/python"
asr_ok=0
for i in $(seq 1 "$ATTEMPTS"); do
    echo "--- SenseVoiceSmall attempt $i/$ATTEMPTS ---"
    if "$ASR_PY" - <<'PYEOF'
from funasr import AutoModel
print("Downloading iic/SenseVoiceSmall via ModelScope (~936 MB)")
AutoModel(model="iic/SenseVoiceSmall", device="cpu", ncpu=1, disable_update=True, disable_pbar=True)
print("  ready")
PYEOF
    then
        asr_ok=1
        break
    fi
    echo "  attempt $i failed — retrying, ModelScope resumes partial downloads"
    sleep 5
done
if [ "$asr_ok" != "1" ]; then
    echo "❌ SenseVoiceSmall download did not complete after $ATTEMPTS attempts — check network"
    exit 1
fi

echo "All AuK models ready (including SenseVoiceSmall ASR). Launch with: bash scripts/start_auk.sh"
