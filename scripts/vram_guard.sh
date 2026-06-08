# vram_guard.sh — preflight VRAM/RAM check for Dragonsuite tool launches (NVIDIA/CUDA).
#
# CANONICAL SOURCE. The dragonsuite-add skill installs an identical copy to
# /srv/containers/edq/scripts/vram_guard.sh, which is the ONE file every
# start_*.sh sources. Improve the gate once here; redeploy; all services benefit.
#
# Source this from a tool's start script BEFORE loading any model. Dragonsuite
# launchers are fire-and-forget (nohup … &) and exit immediately, so the pattern
# is:
#
#   TOOL_NAME=heavytool REQ_VRAM_MIB=13000 REQ_RAM_MIB=4000
#   source scripts/vram_guard.sh
#   vram_preflight                      # warns + aborts if short; CLEAR=1 stops tools I started first
#   nohup python heavytool_server.py >/tmp/heavytool.log 2>&1 &
#   register_tool $!                    # record its PID so CLEAR=1 can stop it cleanly later
#
# Design notes:
#   - The policy ("one heavy tool at a time, light combos allowed") is NOT hardcoded.
#     Each tool declares its real footprint; free-VRAM subtraction decides what may
#     coexist. Give Dragonsight + Z-Image honest small numbers and they launch together;
#     give a 13GB image model an honest number and it refuses while anything heavy is resident.
#   - Single-GPU assumption (uDragon). Macs use unified memory — don't use this there.
#   - This file does NOT change the caller's shell options (no global `set -e`); each
#     function is self-contained and returns explicit codes.
#   - register_tool only WRITES a pidfile — it sets no EXIT trap. Dragonsuite launchers
#     exit the instant they background the server, so a removal-on-EXIT trap would delete
#     the pidfile immediately. Stale pidfiles (dead PID) are reaped lazily by clear_tools
#     / vram_preflight, so nothing leaks.

RUN_DIR="${XDG_RUNTIME_DIR:-$HOME/.dragonsuite/run}"
mkdir -p "$RUN_DIR"

# --- readings -------------------------------------------------------------

_first_line() { printf '%s' "${1%%$'\n'*}"; }

gpu_free_mib() {
  command -v nvidia-smi >/dev/null 2>&1 || { echo "[vram_guard] nvidia-smi not found" >&2; return 1; }
  local out
  # Capture first, then trim: avoids SIGPIPE/pipefail surprises from `| head`.
  out="$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits)" || return 1
  _first_line "$out" | tr -dc '0-9'
}

ram_avail_mib() { awk '/^MemAvailable:/ {printf "%d", $2/1024}' /proc/meminfo; }

gpu_apps() {   # pid, VRAM(MiB), process name of everything currently holding GPU memory
  nvidia-smi --query-compute-apps=pid,used_memory,process_name \
    --format=csv,noheader,nounits 2>/dev/null
}

# --- lifecycle ------------------------------------------------------------

register_tool() {   # call with the launched server's PID; records a pidfile (no EXIT trap)
  : "${TOOL_NAME:?set TOOL_NAME before register_tool}"
  echo "$1" > "$RUN_DIR/${TOOL_NAME}.pid"
}

clear_tools() {     # stop tools we started, gracefully: TERM, escalate to KILL only if ignored
  shopt -s nullglob
  local pf pid n
  for pf in "$RUN_DIR"/*.pid; do
    pid="$(cat "$pf" 2>/dev/null || true)"
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      echo "    stopping $(basename "$pf" .pid) (pid $pid)" >&2
      kill -TERM "$pid" 2>/dev/null || true
      for n in 1 2 3 4 5; do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
      kill -0 "$pid" 2>/dev/null && kill -KILL "$pid" 2>/dev/null || true
    fi
    rm -f "$pf"
  done
}

# --- the gate -------------------------------------------------------------

vram_preflight() {
  local need_v="${REQ_VRAM_MIB:-0}" need_r="${REQ_RAM_MIB:-0}" free_v free_r
  free_v="$(gpu_free_mib)" || { echo "[vram_guard] cannot read GPU; refusing to launch blind." >&2; return 1; }
  free_r="$(ram_avail_mib)"

  if (( free_v >= need_v && free_r >= need_r )); then
    echo "[vram_guard] OK ${TOOL_NAME:-tool}: free ${free_v}MiB VRAM / ${free_r}MiB RAM (need ${need_v}/${need_r})."
    return 0
  fi

  {
    echo "[vram_guard] SHORT for ${TOOL_NAME:-tool}: free ${free_v}MiB VRAM / ${free_r}MiB RAM, need ${need_v}/${need_r}."
    echo "[vram_guard] GPU currently held by:"
    gpu_apps | sed 's/^/    /'
  } >&2

  if [[ "${CLEAR:-0}" == 1 ]]; then
    echo "[vram_guard] CLEAR=1 — stopping tools I started…" >&2
    clear_tools
    free_v="$(gpu_free_mib)"
    if (( free_v >= need_v )); then
      echo "[vram_guard] cleared — ${free_v}MiB free." >&2
      return 0
    fi
    echo "[vram_guard] still short after clear (${free_v}MiB). Aborting." >&2
    return 1
  fi

  echo "[vram_guard] Close the tool(s) above, or relaunch with CLEAR=1 to stop them first." >&2
  return 1
}
