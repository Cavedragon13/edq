#!/bin/bash
# Update skills from upstream, then sync non-gstack skills to reachable machines.
# Runs nightly at 02:15. Only syncs files under 1MB.
# Machines that are offline are skipped gracefully.
#
# Source of truth: udragon ~/.claude/skills/
# Targets: cdragon, odragon, adragon (Macs — path is /Users/edq/.claude/skills/)
#
# gstack is intentionally handled per-machine from GitHub. Do not rsync the
# gstack checkout or gstack-owned live skill folders across machines; filtered
# rsync of .git objects can corrupt the checkout, and setup-generated links are
# host-specific.

set -e

SKILLS_DIR="/home/edq/.claude/skills"
MAC_SKILLS_DIR="/Users/edq/.claude/skills"
MACHINES="cdragon odragon adragon"
MAX_SIZE="1m"  # rsync --max-size filter
LOG_FILE="/srv/containers/edq/logs/sync_skills_cron.log"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

export PATH="/home/edq/.bun/bin:$PATH"

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
        ./setup --host claude --no-prefix >> "$LOG_FILE" 2>&1 || true
        ./setup --host codex --no-prefix >> "$LOG_FILE" 2>&1 || true
        GSTACK_NEW=$(cat "$GSTACK_DIR/VERSION" 2>/dev/null || echo "unknown")
        log "  gstack updated: $GSTACK_OLD → $GSTACK_NEW"
    else
        log "  gstack up to date ($GSTACK_OLD)"
        if [ ! -e "/home/edq/.codex/skills/gstack-qa/SKILL.md" ]; then
            log "  repairing missing Codex gstack links"
            ./setup --host codex --no-prefix >> "$LOG_FILE" 2>&1 || true
        fi
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

# Build an exclude list for every gstack-owned top-level skill. Those entries
# are created by each machine's local gstack setup and must not be rsynced.
GSTACK_EXCLUDES=$(mktemp)
trap 'rm -f "$GSTACK_EXCLUDES"' EXIT
{
    echo "gstack/"
    echo "_gstack-command/"
    echo "connect-chrome/"
    if [ -d "$GSTACK_DIR" ]; then
        find "$GSTACK_DIR" -mindepth 1 -maxdepth 1 -type d -name ".git" -prune -o -type d -exec test -f "{}/SKILL.md" ";" -print \
            | sed 's#.*/##; s#$#/#'
    fi
} | sort -u > "$GSTACK_EXCLUDES"

ensure_remote_gstack() {
    local machine="$1"
    ssh -o ConnectTimeout=5 -o BatchMode=yes "$machine" 'bash -s' <<'REMOTE_GSTACK'
set -e
export PATH="$HOME/.bun/bin:$PATH"
SKILLS_DIR="$HOME/.claude/skills"
BACKUP_DIR="$HOME/.claude/skill-backups"
GSTACK_DIR="$SKILLS_DIR/gstack"
mkdir -p "$SKILLS_DIR" "$BACKUP_DIR"

command -v git >/dev/null 2>&1 || exit 42
command -v bun >/dev/null 2>&1 || exit 43

if [ -e "$GSTACK_DIR" ] && [ ! -d "$GSTACK_DIR/.git" ]; then
    mv "$GSTACK_DIR" "$BACKUP_DIR/gstack-nongit-$(date +%Y%m%d-%H%M%S)"
fi

clone_gstack() {
    rm -rf "$GSTACK_DIR"
    git clone --single-branch --depth 1 https://github.com/garrytan/gstack.git "$GSTACK_DIR" >/dev/null 2>&1
}

if [ ! -d "$GSTACK_DIR/.git" ]; then
    clone_gstack
else
    if ! git -C "$GSTACK_DIR" rev-parse --verify HEAD >/dev/null 2>&1 \
        || ! git -C "$GSTACK_DIR" fetch origin --quiet >/dev/null 2>&1; then
        mv "$GSTACK_DIR" "$BACKUP_DIR/gstack-badgit-$(date +%Y%m%d-%H%M%S)"
        clone_gstack
    else
        cd "$GSTACK_DIR"
        if [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]; then
            if ! git reset --hard origin/main --quiet; then
                cd "$HOME"
                mv "$GSTACK_DIR" "$BACKUP_DIR/gstack-reset-failed-$(date +%Y%m%d-%H%M%S)"
                clone_gstack
            fi
        fi
    fi
fi

cd "$GSTACK_DIR"
./setup --host claude --no-prefix >/tmp/gstack-setup.log 2>&1
./setup --host codex --no-prefix >>/tmp/gstack-setup.log 2>&1

# Older or transitional gstack installs may leave bare command folders in
# ~/.agents/skills. Codex should use ~/.codex/skills/gstack-* links instead.
AGENT_SKILLS_DIR="$HOME/.agents/skills"
if [ -d "$AGENT_SKILLS_DIR" ] && [ -d "$GSTACK_DIR/.agents/skills" ]; then
    AGENT_BACKUP_DIR="$HOME/.agents/skill-backups/gstack-bare-commands-$(date +%Y%m%d-%H%M%S)"
    find "$GSTACK_DIR/.agents/skills" -mindepth 1 -maxdepth 1 -type d -name "gstack-*" -print | while read -r skill_dir; do
        skill_name=$(awk -F': *' '/^name: / { gsub(/^"|"$/, "", $2); print $2; exit }' "$skill_dir/SKILL.md" 2>/dev/null || true)
        candidate="$AGENT_SKILLS_DIR/$skill_name"
        if [ -n "$skill_name" ] && [ -f "$candidate/SKILL.md" ] && grep -q "(gstack)" "$candidate/SKILL.md"; then
            mkdir -p "$AGENT_BACKUP_DIR"
            mv "$candidate" "$AGENT_BACKUP_DIR/$skill_name"
        fi
    done
fi
REMOTE_GSTACK
}

# Resolve symlinks so rsync copies actual content, not broken symlink references
# Use --copy-links to dereference symlinks on send
RSYNC_OPTS=(
    --archive
    --copy-links          # dereference symlinks — send actual content
    --max-size="$MAX_SIZE"
    --delete              # remove skills on remotes that no longer exist locally
    --exclude-from="$GSTACK_EXCLUDES"
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
        log "  → Ensuring gstack on $machine..."
        if ensure_remote_gstack "$machine"; then
            log "    ✓ $machine gstack ready"
        else
            log "    ⚠ $machine gstack setup skipped/failed"
        fi
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
