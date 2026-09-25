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
#   vram_preflight || exit 1            # if short: ComfyUI unload, then stop other registered
#                                       # tools oldest-first until it fits; else refuse (logged)
#   nohup python heavytool_server.py >/tmp/heavytool.log 2>&1 &
#   register_tool $!                    # record its PID so later launches can make room politely
#
# Every make-room action and refusal is appended to logs/vram_guard.log.
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

# Private subfolder: XDG_RUNTIME_DIR itself is shared by the whole desktop session
# (e.g. Ubuntu's update-notifier.pid lives there) and must never be swept.
RUN_DIR="${XDG_RUNTIME_DIR:-$HOME/.dragonsuite/run}/dragonsuite"
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

# --- polite eviction ------------------------------------------------------
# The standard pattern for many models sharing one GPU: admission control +
# evict only what's needed. Only tools THIS gate started (registered pidfiles)
# are ever stopped — never an editor, browser, agent session or unknown process.

GUARD_LOG="${GUARD_LOG:-/srv/containers/edq/logs/vram_guard.log}"
_glog() { printf '%s %s\n' "$(date '+%F %T')" "$*" >> "$GUARD_LOG" 2>/dev/null || true; }

_fits() {           # does this launch fit right now?
  local fv fr
  fv="$(gpu_free_mib)" || return 1
  fr="$(ram_avail_mib)"
  (( fv >= ${REQ_VRAM_MIB:-0} && fr >= ${REQ_RAM_MIB:-0} ))
}

comfy_unload() {    # ask a running ComfyUI to drop cached models; it keeps serving (MCP stays up)
  command -v curl >/dev/null 2>&1 || return 1
  curl -s -m 5 -X POST -H 'Content-Type: application/json' \
    -d '{"unload_models":true,"free_memory":true}' http://127.0.0.1:8188/free >/dev/null 2>&1 || return 1
  sleep 3
}

_vram_of() {        # MiB of GPU memory held by pid (0 if none)
  gpu_apps | awk -F', *' -v p="$1" '$1==p {s+=$2} END {print s+0}'
}

_rss_mib() { awk '/^VmRSS:/ {printf "%d", $2/1024}' "/proc/$1/status" 2>/dev/null || echo 0; }

_worth_stopping() { # only stop a tool if that frees what this launch is short of
  local pid="$1" fv fr
  fv="$(gpu_free_mib)"; fr="$(ram_avail_mib)"
  (( fv < ${REQ_VRAM_MIB:-0} )) && (( $(_vram_of "$pid") > 200 )) && return 0
  (( fr < ${REQ_RAM_MIB:-0} )) && (( $(_rss_mib "$pid") > 1024 )) && return 0
  return 1
}

_stop_pid() {       # TERM, wait up to 10s, KILL only if ignored
  local pid="$1" n
  kill -TERM "$pid" 2>/dev/null || return 0
  for n in 1 2 3 4 5 6 7 8 9 10; do kill -0 "$pid" 2>/dev/null || return 0; sleep 1; done
  kill -KILL "$pid" 2>/dev/null || true
  sleep 2
}

_stop_tool() {      # name pid — stop via the service's OWN stop command (dashboard), else its process group
  # Killing just the GPU-holding pid isn't enough: wrappers can respawn it (ACE-Step's
  # upstream launcher "retries in offline mode" when its python exits).
  local name="$1" pid="$2" pgid mypgid n
  if command -v curl >/dev/null 2>&1 &&
     curl -s -m 30 -X POST "http://127.0.0.1:8100/api/stop/${name}" 2>/dev/null | grep -q '"stopped"'; then
    for n in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do kill -0 "$pid" 2>/dev/null || return 0; sleep 1; done
  fi
  pgid="$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d ' ')"
  mypgid="$(ps -o pgid= -p $$ 2>/dev/null | tr -d ' ')"
  if [[ -n "$pgid" && "$pgid" != "$mypgid" && "$pgid" -gt 1 ]]; then
    kill -TERM -- "-$pgid" 2>/dev/null || true
    for n in 1 2 3 4 5 6 7 8 9 10; do kill -0 "$pid" 2>/dev/null || return 0; sleep 1; done
    kill -KILL -- "-$pgid" 2>/dev/null || true
    sleep 2
  else
    _stop_pid "$pid"
  fi
}

make_room() {       # free just enough: ComfyUI cache first, then registered tools oldest-first
  _fits && return 0
  if comfy_unload && _fits; then
    echo "[vram_guard] made room by asking ComfyUI to unload its cached models." >&2
    _glog "${TOOL_NAME:-tool}: made room via ComfyUI unload"
    return 0
  fi
  shopt -s nullglob
  local pf name pid
  # oldest pidfile first = the tool launched longest ago
  while IFS= read -r pf; do
    name="$(basename "$pf" .pid)"
    [[ "$name" == "${TOOL_NAME:-}" ]] && continue
    [[ "$name" == comfyui ]] && continue        # ComfyUI is unloaded above, never killed (MCP uses it)
    pid="$(cat "$pf" 2>/dev/null || true)"
    if [[ -z "$pid" ]] || ! kill -0 "$pid" 2>/dev/null; then rm -f "$pf"; continue; fi
    _worth_stopping "$pid" || continue           # holds nothing this launch needs — leave it running
    echo "[vram_guard] stopping ${name} (pid ${pid}) to make room for ${TOOL_NAME:-tool}…" >&2
    _glog "${TOOL_NAME:-tool}: stopped ${name} (pid ${pid}) to make room"
    _stop_tool "$name" "$pid"
    rm -f "$pf"
    _fits && return 0
  done < <(ls -1tr "$RUN_DIR"/*.pid 2>/dev/null)
  return 1
}

# --- the gate -------------------------------------------------------------
#   CLEAR unset / auto  (default) polite eviction: make_room, then launch or refuse
#   CLEAR=0             refuse only — never stop anything
#   CLEAR=1             legacy: stop every registered tool first

vram_preflight() {
  local need_v="${REQ_VRAM_MIB:-0}" need_r="${REQ_RAM_MIB:-0}" free_v free_r mode="${CLEAR:-auto}"
  free_v="$(gpu_free_mib)" || { echo "[vram_guard] cannot read GPU; refusing to launch blind." >&2; _glog "${TOOL_NAME:-tool}: REFUSED (cannot read GPU)"; return 1; }
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

  case "$mode" in
    1)
      echo "[vram_guard] CLEAR=1 — stopping every tool I started…" >&2
      clear_tools
      ;;
    0)
      ;;
    *)
      make_room
      ;;
  esac

  if _fits; then
    echo "[vram_guard] OK ${TOOL_NAME:-tool} after making room: free $(gpu_free_mib)MiB VRAM / $(ram_avail_mib)MiB RAM." >&2
    _glog "${TOOL_NAME:-tool}: launched after making room"
    return 0
  fi
  free_v="$(gpu_free_mib)"; free_r="$(ram_avail_mib)"
  echo "[vram_guard] REFUSED ${TOOL_NAME:-tool}: still only ${free_v}MiB VRAM / ${free_r}MiB RAM free (need ${need_v}/${need_r})." >&2
  echo "[vram_guard] What's left isn't a Dragonsuite tool I started — close it (or other apps using RAM) and retry." >&2
  _glog "${TOOL_NAME:-tool}: REFUSED — free ${free_v}/${free_r} MiB VRAM/RAM, need ${need_v}/${need_r}; GPU held by: $(gpu_apps | tr '\n' ';')"
  return 1
}
