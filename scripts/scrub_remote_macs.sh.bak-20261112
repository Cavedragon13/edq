#!/bin/bash
# scrub_remote_macs.sh — run the transcript scrubber on every Mac from udragon.
#
# The secrets list stays on udragon only. For each Mac this script:
#   1. copies scrub_transcripts.py to ~/.cache/dragon-scrub/ (so the Mac always
#      runs the same version as udragon), then
#   2. runs it over SSH with the credentials piped into stdin (--creds-stdin).
# Nothing secret is written to disk on the Mac and nothing appears in argv.
#
# Tries the LAN name first, then the Tailscale name, so a travelling Mac is
# still reached. An unreachable Mac is logged and caught on the next night.
# Called from backup_claude_files.sh (nightly, 02:10).

set -uo pipefail

SCRIPT="/srv/containers/edq/scripts/scrub_transcripts.py"
CREDS="$HOME/.claude/scrub-credentials.txt"
REMOTE_DIR=".cache/dragon-scrub"
HOSTS=(cdragon odragon adragon)
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=8)

# Pick a working Python on the Mac. odragon's /usr/bin/python3 stub refuses to
# run until the Xcode licence is accepted, so Homebrew builds are tried first.
REMOTE_RUN='for p in /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
  if "$p" -c "import sys" >/dev/null 2>&1; then exec "$p" "$HOME/'"$REMOTE_DIR"'/scrub_transcripts.py" --creds-stdin; fi
done
echo "  ERROR: no working python3 found" >&2; exit 3'

if [ ! -r "$CREDS" ]; then
    echo "  ERROR: $CREDS not readable; skipping Mac scrub"
    exit 1
fi

failures=0
for host in "${HOSTS[@]}"; do
    target=""
    for candidate in "$host" "${host}-ts"; do
        if ssh "${SSH_OPTS[@]}" "$candidate" true >/dev/null 2>&1; then
            target="$candidate"
            break
        fi
    done

    if [ -z "$target" ]; then
        echo "  [$host] unreachable (LAN and Tailscale); will retry next run"
        failures=$((failures + 1))
        continue
    fi

    echo "  [$host] via $target"
    if ! ssh "${SSH_OPTS[@]}" "$target" "mkdir -p \"\$HOME/$REMOTE_DIR\" && chmod 700 \"\$HOME/$REMOTE_DIR\"" \
        || ! scp -q "${SSH_OPTS[@]}" "$SCRIPT" "$target:$REMOTE_DIR/scrub_transcripts.py"; then
        echo "  [$host] could not copy scrubber"
        failures=$((failures + 1))
        continue
    fi

    if ! ssh "${SSH_OPTS[@]}" "$target" "$REMOTE_RUN" < "$CREDS" 2>&1 | sed "s/^/  [$host] /"; then
        failures=$((failures + 1))
    fi
done

echo "  Mac scrub finished with $failures problem(s)"
exit 0
