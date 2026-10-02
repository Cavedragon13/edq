#!/bin/bash
# Pre-download the ONNX weights for every model Rembg's server.py exposes
# (scripts/rembg_server.py MODELS dict), so first launch does not fetch them.
# rembg caches to ~/.u2net by default; new_session() is a no-op download if
# the file is already there, so this script is safe to re-run.
set -e
cd /srv/containers/edq
VENV="venv_rembg"
source scripts/dragonsuite_lib.sh
activate_venv "$VENV"

python3 - <<'PYEOF'
from rembg import new_session

models = ["isnet-general-use", "u2net", "u2net_human_seg", "isnet-anime", "silueta", "u2netp"]
for name in models:
    print(f"Ensuring {name} ...")
    new_session(name)
print("All Rembg models present.")
PYEOF
