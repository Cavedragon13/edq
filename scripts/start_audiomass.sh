#!/bin/bash
# AudioMass — Web Audio Editor (client-side waveform editor)
# Port: 8027
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="AudioMass"
PORT=8027
SRC_DIR="/srv/containers/edq/projects/AudioMass/src"

service_header "$SERVICE_NAME" "$PORT"

if [ ! -f "$SRC_DIR/index.html" ]; then
    echo "❌ AudioMass not found at $SRC_DIR"
    echo "   Clone it first:"
    echo "   cd /srv/containers/edq/projects && git clone https://github.com/pkalogiros/AudioMass.git"
    exit 1
fi

clear_port "$PORT"

echo "🚀 Starting $SERVICE_NAME..."

if pgrep -f "http.server" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup python3 -m http.server "$PORT" --directory "$SRC_DIR" > /tmp/audiomass.log 2>&1 &
    if wait_for_port "$PORT" 10; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
        echo ""
        echo "Features:"
        echo "  - Waveform editing (cut, copy, paste, trim, reverse, invert)"
        echo "  - Audio effects (fade, compressor, normalize, reverb, delay, pitch shift)"
        echo "  - Fully client-side (no server uploads, privacy-focused)"
        echo "  - Spectrum analyzer + peak detection"
        echo "  - Export to MP3/WAV/FLAC"
        echo "  - 20+ keyboard shortcuts"
    else
        echo "❌ Failed — check /tmp/audiomass.log"
        tail -10 /tmp/audiomass.log
        exit 1
    fi
fi
