#!/bin/bash
# nightly_commit.sh — Auto-commit config and script changes
# Runs nightly at 0200 local (via cron).
# Covers four repos: edq, claude-config (~/.claude), claude skills, knowledge-base.
# Never touches models/, cache_*, *.safetensors, *.bin, *.pkl
#
# Secret gate (added 2026-09-23): every repo's staged changes are scanned with
# gitleaks before committing. If anything is found, that repo is unstaged and
# skipped for the night (nothing committed, nothing pushed), the finding is
# logged with the secret redacted, and the other repos carry on.
# Review: /srv/containers/edq/logs/gitleaks/<label>-<date>.json

set -e
LOG="/srv/containers/edq/logs/nightly_commit.log"
LEAK_DIR="/srv/containers/edq/logs/gitleaks"
GITLEAKS="/home/edq/.local/bin/gitleaks"
mkdir -p "$(dirname "$LOG")" "$LEAK_DIR"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

# Scan what is staged in the current repo. Returns 0 when clean, 1 when a
# secret was found (index is reset so nothing gets committed). Fails closed:
# if gitleaks is missing or errors, the repo is skipped rather than pushed blind.
secret_gate() {
    local label="$1"
    local report="$LEAK_DIR/${label}-$(date '+%Y-%m-%d').json"

    if [ ! -x "$GITLEAKS" ]; then
        log "[$label] BLOCKED: gitleaks not found at $GITLEAKS — not committing"
        git reset -q
        return 1
    fi

    local rc=0
    "$GITLEAKS" git --pre-commit --staged --redact --no-banner -l error \
        -f json -r "$report" . >> "$LOG" 2>&1 || rc=$?

    if [ "$rc" -eq 0 ]; then
        rm -f "$report"
        return 0
    fi

    git reset -q
    if [ "$rc" -eq 1 ]; then
        log "[$label] BLOCKED: gitleaks found possible secrets — nothing committed. Details (redacted): $report"
        python3 - "$report" >> "$LOG" 2>&1 <<'PYEOF' || true
import json, sys
for f in json.load(open(sys.argv[1])):
    print(f"    {f['RuleID']:28} {f['File']}:{f['StartLine']}")
PYEOF
    else
        log "[$label] BLOCKED: gitleaks exited with error $rc — nothing committed"
    fi
    return 1
}

# Commit whatever is staged in the current repo, after the secret gate.
# Second argument "push-if-remote" only pushes when an origin exists.
commit_staged() {
    local label="$1"
    local push_mode="${2:-push}"

    if git diff --cached --quiet; then
        log "[$label] Nothing to commit"
        return 0
    fi

    secret_gate "$label" || return 0

    local CHANGED
    CHANGED=$(git diff --cached --name-only | wc -l)
    local MSG="chore: nightly auto-commit ($(date '+%Y-%m-%d'), $CHANGED file(s))"
    git commit -m "$MSG" >> "$LOG" 2>&1
    log "[$label] Committed $CHANGED file(s)"

    if [ "$push_mode" = "push-if-remote" ] && ! git remote get-url origin > /dev/null 2>&1; then
        log "[$label] No origin remote; committed locally only"
        return 0
    fi
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

commit_staged edq

# --- claude-config repo (~/.claude) ---
cd /home/edq/.claude
if git rev-parse --git-dir > /dev/null 2>&1; then
    git add CLAUDE.md SKILLS.md settings.json settings.local.json plans/ 2>/dev/null || true
    git add "projects/-srv-containers-edq/memory/" 2>/dev/null || true
    commit_staged claude
else
    log "[claude] Not a git repo, skipping"
fi

# --- claude skills repo (~/.claude/skills) ---
cd /home/edq/.claude/skills
if git rev-parse --git-dir > /dev/null 2>&1; then
    # Keep the local closeout SOP durable without committing the whole noisy skills tree.
    git add llkb/SKILL.md 2>/dev/null || true
    commit_staged skills push-if-remote
else
    log "[skills] Not a git repo, skipping"
fi

# --- knowledge-base repo ---
cd /home/edq/knowledge-base
if git rev-parse --git-dir > /dev/null 2>&1; then
    git add -A 2>/dev/null || true
    commit_staged kb
else
    log "[kb] Not a git repo, skipping"
fi
