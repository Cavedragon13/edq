#!/bin/bash
# stop_tool.sh — stop Dragonsuite tools by the PID their launcher registered, never by name.
#
#   bash scripts/stop_tool.sh <TOOL_NAME> [<TOOL_NAME> ...]
#
# Launchers that source scripts/vram_guard.sh call `register_tool $!`, which writes
# $XDG_RUNTIME_DIR/dragonsuite/<TOOL_NAME>.pid. This script TERMs that PID (its whole
# process group when the launcher used setsid, otherwise the PID and its descendants),
# waits, escalates to KILL, removes the pidfile, and exits 0 even if nothing was running.
#
# Why: the old stop_commands were `pkill -f '<script>.py'`, which also matched — and
# killed — any unrelated shell whose command line mentioned the script (e.g. a Claude Code
# bash call running sed or py_compile on it). The dashboard still kills whatever is left
# on the service's port afterwards, which covers a service started without its launcher.
# Several names are stopped in parallel so multi-process services stay inside the
# dashboard's stop timeout.
cd /srv/containers/edq || exit 1
# shellcheck source=vram_guard.sh
source scripts/vram_guard.sh
[[ $# -ge 1 ]] || { echo "usage: stop_tool.sh <TOOL_NAME> [...]" >&2; exit 2; }
for name in "$@"; do stop_registered "$name" & done
wait
exit 0
