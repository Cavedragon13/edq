#!/bin/bash
# Pre-download Dolphin Vision 7B (run once before first launch). Never let
# the first launch pull these silently.
#
# scripts/dolphin_vision_server.py loads from MODEL_PATH = models/dolphin-vision-7b
# with local_files_only=True — repo id confirmed via HF Hub search (model card
# text alone named the wrong namespace): dphn/dolphin-vision-7b.
set -e
cd /srv/containers/edq
PY="/srv/containers/edq/venv_dolphin_vision/bin/python"
[ -x "$PY" ] && "$PY" -c "import huggingface_hub" 2>/dev/null || PY="/srv/containers/edq/venv_dragonsuite/bin/python"

ATTEMPTS="${DOLPHIN_VISION_DOWNLOAD_ATTEMPTS:-15}"

ok=0
for i in $(seq 1 "$ATTEMPTS"); do
    echo "--- attempt $i/$ATTEMPTS (dphn/dolphin-vision-7b) ---"
    if "$PY" - <<'PYEOF'
from huggingface_hub import snapshot_download

snapshot_download(
    repo_id="dphn/dolphin-vision-7b",
    local_dir="/srv/containers/edq/models/dolphin-vision-7b",
    ignore_patterns=["*.md", ".gitattributes"],
)
print("Dolphin Vision 7B ready.")
PYEOF
    then
        ok=1
        break
    fi
    echo "  attempt $i failed (likely a dropped connection) — retrying, resuming from partial bytes"
    sleep 5
done
if [ "$ok" != "1" ]; then
    echo "❌ Dolphin Vision 7B download did not complete after $ATTEMPTS attempts — check network"
    exit 1
fi

echo "Dolphin Vision 7B ready. Launch with: bash scripts/start_dolphin_vision_native.sh"
