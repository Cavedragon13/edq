#!/bin/bash
# Update skills from upstream, then sync to all reachable machines.
# Runs nightly at 02:15. Only syncs files under 1MB.
# Machines that are offline are skipped gracefully.
#
# Source of truth: udragon ~/.claude/skills/
# Targets: cdragon, odragon, adragon (Macs — path is /Users/edq/.claude/skills/)

set -e

SKILLS_DIR="/home/edq/.claude/skills"
MAC_SKILLS_DIR="/Users/edq/.claude/skills"
MACHINES="cdragon odragon adragon"
MAX_SIZE="1m"  # rsync --max-size filter

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

# ── Step 1: Update gstack (git-based) ────────────────────────────────────────
log "Checking gstack for updates..."
GSTACK_DIR="$SKILLS_DIR/gstack"
if [ -d "$GSTACK_DIR/.git" ]; then
    GSTACK_OLD=$(cat "$GSTACK_DIR/VERSION" 2>/dev/null || echo "unknown")
    cd "$GSTACK_DIR"
    git fetch origin --quiet 2>&1 || true
    LOCAL=$(git rev-parse HEAD)
    REMOTE=$(git rev-parse origin/main)
    if [ "$LOCAL" != "$REMOTE" ]; then
        git reset --hard origin/main --quiet
        ./setup >> /srv/containers/edq/logs/sync_skills_cron.log 2>&1 || true
        GSTACK_NEW=$(cat "$GSTACK_DIR/VERSION" 2>/dev/null || echo "unknown")
        log "  gstack updated: $GSTACK_OLD → $GSTACK_NEW"
    else
        log "  gstack up to date ($GSTACK_OLD)"
    fi
    cd - > /dev/null
else
    log "  gstack: not a git install, skipping"
fi

# ── Step 2: Update registry skills (npx skills) ──────────────────────────────
log "Checking registry skills for updates..."
export PATH="/home/edq/.nvm/versions/node/$(ls /home/edq/.nvm/versions/node/ | sort -V | tail -1)/bin:$PATH"
if command -v npx > /dev/null 2>&1; then
    UPDATE_OUT=$(npx skills update --global --yes 2>&1 || true)
    UPDATED=$(echo "$UPDATE_OUT" | grep "Updated " | tail -1)
    if [ -n "$UPDATED" ]; then
        log "  $UPDATED"
    else
        log "  Registry skills up to date"
    fi
else
    log "  npx not found, skipping registry update"
fi

log "Starting skills sync from udragon..."
log "Source: $SKILLS_DIR"

# Resolve symlinks so rsync copies actual content, not broken symlink references
# Use --copy-links to dereference symlinks on send
RSYNC_OPTS=(
    --archive
    --copy-links          # dereference symlinks — send actual content
    --max-size="$MAX_SIZE"
    --delete              # remove skills on remotes that no longer exist locally
    --exclude="node_modules/"  # platform-specific — each machine builds its own
    --exclude="*/dist/"        # compiled binaries — each machine builds its own
    --exclude="*.pyc"
    --exclude=".DS_Store"
    --timeout=15
    --quiet
)

synced=0
skipped=0

for machine in $MACHINES; do
    if ssh -o ConnectTimeout=5 -o BatchMode=yes "$machine" true 2>/dev/null; then
        log "  → Syncing to $machine..."
        # Ensure target dir exists
        ssh "$machine" mkdir -p "$MAC_SKILLS_DIR" 2>/dev/null
        if rsync "${RSYNC_OPTS[@]}" "$SKILLS_DIR/" "${machine}:${MAC_SKILLS_DIR}/"; then
            log "    ✓ $machine synced"
            synced=$((synced + 1))
        else
            log "    ✗ $machine rsync failed (exit $?)"
        fi
    else
        log "  ○ $machine unreachable, skipping"
        skipped=$((skipped + 1))
    fi
done

log "Skills sync complete. Synced: $synced, Skipped (offline): $skipped"
