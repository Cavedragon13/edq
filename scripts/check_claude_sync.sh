#!/bin/bash
# SOP: verify every machine's ~/.claude/CLAUDE.md symlink resolves correctly
# AND that Syncthing has the knowledge-base folder fully synced (idle, 0 needBytes,
# 0 errors) on that machine. Since CLAUDE.md is a symlink into the Syncthing-synced
# vault, a synced folder + valid symlink together guarantee current content —
# no separate content diff needed (that's what the old SMB-era version of this
# script did; superseded 2026-06-24 when claude-sync moved onto Syncthing).
#
# Syncthing API keys are NOT stored here (changed 2026-09-23 — they were hardcoded
# and this repo is public). Each machine reads its own key from its own Syncthing
# config at run time, and the key never leaves that machine.
#
# See knowledge-base/Directions/Sharing Claude Code Context Across Machines.md
# Runs daily via cron. Machines that are offline are skipped, not failed.

CANONICAL_LINK_TARGET="/home/edq/knowledge-base/claude-sync/global-CLAUDE.md"
MAC_LINK_TARGET="/Users/edq/knowledge-base/claude-sync/global-CLAUDE.md"
MACHINES="cdragon odragon adragon"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

# Runs ON the machine being checked (locally or via ssh). Finds Syncthing's
# config, reads the API key from it, queries the local REST API, and prints the
# raw folder-status JSON. Linux keeps config in ~/.local/state/syncthing (or the
# older ~/.config/syncthing); macOS in ~/Library/Application Support/Syncthing.
read -r -d '' STATUS_PROBE <<'PROBE'
for c in "$HOME/.local/state/syncthing/config.xml" \
         "$HOME/.config/syncthing/config.xml" \
         "$HOME/Library/Application Support/Syncthing/config.xml"; do
    if [ -f "$c" ]; then
        key=$(sed -n 's:.*<apikey>\(.*\)</apikey>.*:\1:p' "$c" | head -1)
        break
    fi
done
if [ -z "${key:-}" ]; then
    echo '{"probe_error":"no Syncthing config or API key found"}'
    exit 0
fi
curl -s -H "X-API-Key: $key" 'http://127.0.0.1:8384/rest/db/status?folder=knowledge-base'
PROBE

check_folder_status() {
    local host="$1"
    local json
    if [ "$host" = "local" ]; then
        json=$(bash -c "$STATUS_PROBE" 2>/dev/null)
    else
        json=$(ssh -o BatchMode=yes "$host" 'bash -s' <<< "$STATUS_PROBE" 2>/dev/null)
    fi
    printf '%s' "$json" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    if 'probe_error' in d:
        print('NOTOK ' + d['probe_error'])
        sys.exit()
    ok = d.get('state') == 'idle' and d.get('needBytes', -1) == 0 and d.get('errors', -1) == 0 and d.get('pullErrors', -1) == 0
    print('OK' if ok else f\"NOTOK state={d.get('state')} needBytes={d.get('needBytes')} errors={d.get('errors')} pullErrors={d.get('pullErrors')}\")
except Exception as e:
    print(f'NOTOK parse_error={e}')
"
}

drift=0
offline=0

# --- udragon ---
log "Checking udragon..."
if [ -L /home/edq/.claude/CLAUDE.md ] && [ "$(readlink -f /home/edq/.claude/CLAUDE.md)" = "$(readlink -f "$CANONICAL_LINK_TARGET")" ]; then
    ST_STATUS=$(check_folder_status local)
    if [ "$ST_STATUS" = "OK" ]; then
        log "  ✓ udragon symlink OK, Syncthing folder synced"
    else
        log "  ✗ udragon: Syncthing folder not synced — $ST_STATUS"
        drift=$((drift + 1))
    fi
else
    log "  ✗ udragon: ~/.claude/CLAUDE.md is NOT a symlink to $CANONICAL_LINK_TARGET — FIX MANUALLY"
    drift=$((drift + 1))
fi

for machine in $MACHINES; do
    if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "$machine" true 2>/dev/null; then
        log "  ○ $machine unreachable, skipping"
        offline=$((offline + 1))
        continue
    fi

    log "Checking $machine..."

    LINK_TARGET=$(ssh "$machine" "readlink ~/.claude/CLAUDE.md" 2>/dev/null)
    if [ "$LINK_TARGET" != "$MAC_LINK_TARGET" ]; then
        log "  ✗ $machine: symlink is '$LINK_TARGET', expected '$MAC_LINK_TARGET'"
        drift=$((drift + 1))
        continue
    fi

    ST_STATUS=$(check_folder_status "$machine")
    if [ "$ST_STATUS" != "OK" ]; then
        log "  ✗ $machine: Syncthing folder not synced — $ST_STATUS (check brew services list / launchctl)"
        drift=$((drift + 1))
        continue
    fi

    log "  ✓ $machine symlink OK, Syncthing folder synced"
done

log "Done. Drifted/broken: $drift, Offline: $offline"

if [ "$drift" -gt 0 ]; then
    exit 1
fi
