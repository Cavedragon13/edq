#!/bin/bash
# nightly_commit.sh — Auto-commit config and script changes
# Runs nightly at 0200 local (via cron).
# Never touches models/, cache_*, *.safetensors, *.bin, *.pkl

set -e
REPO="/srv/containers/edq"
LOG="/srv/containers/edq/logs/nightly_commit.log"
mkdir -p "$(dirname "$LOG")"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

cd "$REPO"

# Bail if not a git repo
git rev-parse --git-dir > /dev/null 2>&1 || { log "Not a git repo, skipping"; exit 0; }

# Stage: tracked files that changed + known config/script paths (no models/cache)
# Use nullglob so non-matching globs (e.g. media/*.css) expand to nothing
# instead of passing a literal string to git (which causes git to fail the
# entire add operation, silently dropping all staged files).
shopt -s nullglob
git add \
    CLAUDE.md \
    .mcp.json \
    config/ \
    docs/ \
    scripts/ \
    mcp-servers/ \
    media/*.html \
    media/*.js \
    media/*.css \
    media/*.svg \
    media/favicons/ \
    2>/dev/null || true
shopt -u nullglob

# Skip if nothing staged
if git diff --cached --quiet; then
    log "Nothing to commit"
    exit 0
fi

CHANGED=$(git diff --cached --name-only | wc -l)
MSG="chore: nightly auto-commit ($(date '+%Y-%m-%d'), $CHANGED file(s))"

git commit -m "$MSG" >> "$LOG" 2>&1
log "Committed $CHANGED file(s): $MSG"
