#!/bin/bash
# SenseNova-U1.5-8B-MoT — native unified multimodal T2I (Q8 GGUF + balanced layer-offload)
# Port: 8048
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

# Honest footprint — Q8 GGUF (19.9GB on disk) run with vram_mode=balanced and
# fast_vram_budget_gib=12 (see scripts/sensenova_server.py), so only a working
# set of layers is resident at once. 13500 keeps margin above the 12GB budget
# for activations; adjust after the first real generation is profiled.
#
# CONFIRMED INFEASIBLE on this machine as of 2026-08-24 — do not lower
# REQ_RAM_MIB back down without new evidence. Two real launch attempts both
# blew through available RAM into swap exhaustion and had to be killed:
#   1) ~21GB available (normal desktop load) — swap maxed (7.97/8GB) at ~half
#      the GGUF loaded, killed at ~90s.
#   2) ~24.8GB available (after closing all but one Chrome tab) — got further,
#      but swap still went from 2.7GB free to ~0 in a single 10s tick near the
#      end and had to be killed.
# gguf_loader.py's `torch.from_numpy(tensor.data.copy())` forces the full
# ~20GB GGUF into real (non-file-backed) RAM regardless of vram_mode (that
# flag is GPU-offload-only, not CPU-side) — see docs/venvs.md 2026-08-24 entry.
# Real peak is estimated ~28-30GB given attempt #2 still failed with 24.8GB
# free. REQ_RAM_MIB is set above the observed failure point specifically so
# this launcher refuses rather than repeating the swap-exhaustion crash; do
# not attempt to "fix" this by lowering it.
TOOL_NAME="sensenova"
REQ_VRAM_MIB=13500
REQ_RAM_MIB=30000
source scripts/vram_guard.sh

SERVICE_NAME="SenseNova-U1.5-8B-MoT"
PORT=8048
VENV="venv_sensenova"
APP_DIR="$DRAGONSUITE_ROOT/projects/SenseNova-U1"
CONFIG_DIR="/srv/containers/edq/models/sensenova-u1.5"
GGUF_FILE="/srv/containers/edq/models/sensenova-u1.5/gguf/SenseNova-U1.5-8B-MoT-Preview-Q8.gguf"

service_header "$SERVICE_NAME" "$PORT"

if [ ! -d "$APP_DIR" ]; then
    echo "❌ Project not found: $APP_DIR"
    echo "   git clone --branch feat/u1.5 https://github.com/OpenSenseNova/SenseNova-U1.git projects/SenseNova-U1"
    exit 1
fi
if [ ! -f "$CONFIG_DIR/config.json" ] || [ ! -f "$GGUF_FILE" ]; then
    echo "❌ Model assets not found under $CONFIG_DIR"
    echo "   Run: bash scripts/download_sensenova_models.sh"
    exit 1
fi

vram_preflight || exit 1
clear_port "$PORT"
activate_venv "$VENV"
set_pytorch_env

echo "🚀 Starting $SERVICE_NAME..."
if pgrep -f "sensenova_server.py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup python scripts/sensenova_server.py --port "$PORT" > /tmp/sensenova.log 2>&1 &
    register_tool $!
    echo "⏳ Waiting for service (8B model load + GGUF dequant takes a while)..."
    if wait_for_port "$PORT" 300; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Not up in time — check /tmp/sensenova.log"
        tail -20 /tmp/sensenova.log
        exit 1
    fi
fi
