#!/bin/bash
# lint_knowledge_base.sh — Format markdown KB files with prettier
# Runs: manually, or 1st of month at 0400 local (via cron)
set -e

LOG_FILE="/srv/containers/edq/logs/lint_kb_$(date +%Y%m).log"
mkdir -p "$(dirname "$LOG_FILE")"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

PRETTIER="npx --yes prettier"
PRETTIER_OPTS="--write --prose-wrap preserve --print-width 120"

# Files to lint — explicit list, not recursive, to avoid touching
# Obsidian wiki-links or other non-standard markdown
TARGETS=(
    "/home/edq/.claude/CLAUDE.md"
    "/home/edq/.claude/projects/-srv-containers-edq/memory/MEMORY.md"
    /home/edq/.claude/projects/-srv-containers-edq/memory/*.md
    "/srv/containers/edq/CLAUDE.md"
    /srv/containers/edq/docs/*.md
    /srv/containers/edq/docs/services/*.md
)

log "Starting KB lint"
changed=0
errors=0

for f in "${TARGETS[@]}"; do
    [[ -f "$f" ]] || continue
    f=$(readlink -f "$f")  # resolve symlinks — prettier won't write to them
    before=$(md5sum "$f" | cut -d' ' -f1)
    if $PRETTIER $PRETTIER_OPTS "$f" >> "$LOG_FILE" 2>&1; then
        after=$(md5sum "$f" | cut -d' ' -f1)
        if [[ "$before" != "$after" ]]; then
            log "  CHANGED: $f"
            ((changed++)) || true
        fi
    else
        log "  ERROR:   $f"
        ((errors++)) || true
    fi
done

log "Done — $changed file(s) changed, $errors error(s)"
