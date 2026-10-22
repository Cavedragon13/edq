#!/bin/bash
# Pre-download the Faster-Whisper model (run once before first launch). Never
# let the first launch pull this silently.
#
# src/pipeline/preprocess.py hardcodes whisper_model_size="base", device="cpu"
# (no GPU use — runs on CPU only). faster_whisper.utils.download_model resolves
# size "base" to repo id Systran/faster-whisper-base (confirmed by reading
# faster_whisper/utils.py's _MODELS table directly, not the model card).
set -e
cd /srv/containers/edq
PY="/srv/containers/edq/venv_agentic_video/bin/python"

ATTEMPTS="${AGENTIC_VIDEO_DOWNLOAD_ATTEMPTS:-15}"

ok=0
for i in $(seq 1 "$ATTEMPTS"); do
    echo "--- attempt $i/$ATTEMPTS (Systran/faster-whisper-base) ---"
    if "$PY" -c "from faster_whisper.utils import download_model; download_model('base'); print('Faster-Whisper base model ready.')"
    then
        ok=1
        break
    fi
    echo "  attempt $i failed (likely a dropped connection) — retrying, resuming from partial bytes"
    sleep 5
done
if [ "$ok" != "1" ]; then
    echo "❌ Faster-Whisper base model download did not complete after $ATTEMPTS attempts — check network"
    exit 1
fi

echo "Agentic Video Editor models ready. Launch with: bash scripts/start_agentic_video.sh"
