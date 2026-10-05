#!/bin/bash
# Pre-download FaceFusion models (run once before first launch). Never let the
# first launch pull these silently.
#
# FaceFusion ships its own downloader (`facefusion.py force-download`), which
# is what `facefusion.py run` would otherwise trigger lazily per-processor on
# first use. --download-scope lite matches the CLI's own default (see
# facefusion/program.py: default = 'lite') — the same set `run` pulls with no
# extra flags. Safe to re-run: it's a no-op once .assets/ is populated (checks
# existing file hashes before re-fetching).
set -e
cd /srv/containers/edq/projects/facefusion
PY="/srv/containers/edq/venv_facefusion/bin/python"

"$PY" facefusion.py force-download --download-scope lite --log-level info

echo "FaceFusion models ready (lite scope). Launch with: bash scripts/start_facefusion.sh"
