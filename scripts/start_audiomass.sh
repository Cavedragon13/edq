#!/bin/bash
set -e

echo "🎵 Starting AudioMass Web Audio Editor..."

SRC_DIR="/srv/containers/edq/projects/AudioMass/src"

if [ ! -f "$SRC_DIR/index.html" ]; then
    echo "❌ AudioMass not found at $SRC_DIR"
    echo "Clone it first:"
    echo "  cd /srv/containers/edq/projects && git clone https://github.com/pkalogiros/AudioMass.git"
    exit 1
fi

cd "$SRC_DIR"

echo "✓ Launching on port 8027..."
echo "📍 Access at: http://192.168.7.226:8027"
echo ""
echo "Features:"
echo "  - Waveform editing (cut, copy, paste, trim, reverse, invert)"
echo "  - Audio effects (fade, compressor, normalize, reverb, delay, pitch shift)"
echo "  - Fully client-side (no server uploads, privacy-focused)"
echo "  - Spectrum analyzer + peak detection"
echo "  - Export to MP3/WAV/FLAC"
echo "  - 20+ keyboard shortcuts"
echo ""

python3 -m http.server 8027
