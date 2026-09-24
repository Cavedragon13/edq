#!/bin/bash
# nightly_commit.sh — Auto-commit config and script changes
# Runs nightly at 0200 local (via cron).
# Covers three repos: edq, claude-config (~/.claude), knowledge-base.
# Never touches models/, cache_*, *.safetensors, *.bin, *.pkl

set -e
LOG="/srv/containers/edq/logs/nightly_commit.log"
mkdir -p "$(dirname "$LOG")"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

commit_and_push() {
    local repo="$1"
    local label="$2"

    cd "$repo"
    git rev-parse --git-dir > /dev/null 2>&1 || { log "[$label] Not a git repo, skipping"; return 0; }

    if git diff --cached --quiet && git diff --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]; then
        log "[$label] Nothing to commit"
        return 0
    fi

    git add -u 2>/dev/null || true

    if git diff --cached --quiet; then
        log "[$label] Nothing staged"
        return 0
    fi

    local CHANGED
    CHANGED=$(git diff --cached --name-only | wc -l)
    local MSG="chore: nightly auto-commit ($(date '+%Y-%m-%d'), $CHANGED file(s))"

    git commit -m "$MSG" >> "$LOG" 2>&1
    log "[$label] Committed $CHANGED file(s)"

    git push origin master >> "$LOG" 2>&1 && log "[$label] Pushed to GitHub" || log "[$label] WARNING: push failed"
}

# --- edq repo ---
cd /srv/containers/edq
git rev-parse --git-dir > /dev/null 2>&1 || { log "[edq] Not a git repo, skipping"; exit 0; }

shopt -s nullglob
git add \
    CLAUDE.md \
    AGENTS.md \
    .mcp.json \
    config/ \
    docs/ \
    scripts/ \
    mcp-servers/ \
    tasks/lessons.md \
    media/*.html \
    media/*.js \
    media/*.css \
    media/*.svg \
    media/favicons/ \
    2>/dev/null || true
shopt -u nullglob

if git diff --cached --quiet; then
    log "[edq] Nothing to commit"
else
    CHANGED=$(git diff --cached --name-only | wc -l)
    MSG="chore: nightly auto-commit ($(date '+%Y-%m-%d'), $CHANGED file(s))"
    git commit -m "$MSG" >> "$LOG" 2>&1
    log "[edq] Committed $CHANGED file(s)"
    git push origin master >> "$LOG" 2>&1 && log "[edq] Pushed to GitHub" || log "[edq] WARNING: push failed"
fi

# --- claude-config repo (~/.claude) ---
cd /home/edq/.claude
git rev-parse --git-dir > /dev/null 2>&1 || { log "[claude] Not a git repo, skipping"; }

if git rev-parse --git-dir > /dev/null 2>&1; then
    git add CLAUDE.md SKILLS.md settings.json settings.local.json plans/ 2>/dev/null || true
    git add "projects/-srv-containers-edq/memory/" 2>/dev/null || true

    if ! git diff --cached --quiet; then
        CHANGED=$(git diff --cached --name-only | wc -l)
        MSG="chore: nightly auto-commit ($(date '+%Y-%m-%d'), $CHANGED file(s))"
        git commit -m "$MSG" >> "$LOG" 2>&1
        log "[claude] Committed $CHANGED file(s)"
        git push origin master >> "$LOG" 2>&1 && log "[claude] Pushed to GitHub" || log "[claude] WARNING: push failed"
    else
        log "[claude] Nothing to commit"
    fi
fi

# --- claude skills repo (~/.claude/skills) ---
cd /home/edq/.claude/skills
git rev-parse --git-dir > /dev/null 2>&1 || { log "[skills] Not a git repo, skipping"; }

if git rev-parse --git-dir > /dev/null 2>&1; then
    # Keep the local closeout SOP durable without committing the whole noisy skills tree.
    git add llkb/SKILL.md 2>/dev/null || true

    if ! git diff --cached --quiet; then
        CHANGED=$(git diff --cached --name-only | wc -l)
        MSG="chore: nightly auto-commit ($(date '+%Y-%m-%d'), $CHANGED file(s))"
        git commit -m "$MSG" >> "$LOG" 2>&1
        log "[skills] Committed $CHANGED file(s)"
        if git remote get-url origin > /dev/null 2>&1; then
            git push origin master >> "$LOG" 2>&1 && log "[skills] Pushed to GitHub" || log "[skills] WARNING: push failed"
        else
            log "[skills] No origin remote; committed locally only"
        fi
    else
        log "[skills] Nothing to commit"
    fi
fi

# --- knowledge-base repo ---
cd /home/edq/knowledge-base
git rev-parse --git-dir > /dev/null 2>&1 || { log "[kb] Not a git repo, skipping"; }

if git rev-parse --git-dir > /dev/null 2>&1; then
    git add -A 2>/dev/null || true

    if ! git diff --cached --quiet; then
        CHANGED=$(git diff --cached --name-only | wc -l)
        MSG="chore: nightly auto-commit ($(date '+%Y-%m-%d'), $CHANGED file(s))"
        git commit -m "$MSG" >> "$LOG" 2>&1
        log "[kb] Committed $CHANGED file(s)"
        git push origin master >> "$LOG" 2>&1 && log "[kb] Pushed to GitHub" || log "[kb] WARNING: push failed"
    else
        log "[kb] Nothing to commit"
    fi
fi
