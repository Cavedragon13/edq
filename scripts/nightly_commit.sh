#!/bin/bash
# nightly_commit.sh — Auto-commit Dragonsuite source changes
# Runs nightly at 0200 local (via cron).
# Covers the edq config repo, every independent source repo in dragonsuite.json,
# claude-config (~/.claude), claude skills, and knowledge-base.
# Set NIGHTLY_COMMIT_SCOPE=dragonsuite to run only registered service paths.
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
ATTENTION_FILE="/srv/containers/edq/logs/nightly_commit_attention.md"
ATTENTION_ROWS=""
mkdir -p "$(dirname "$LOG")" "$LEAK_DIR"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }
attention() { ATTENTION_ROWS+="| $1 | $2 |\n"; }

# Scan what is staged in the current repo. Returns 0 when clean, 1 when a
# secret was found (index is reset so nothing gets committed). Fails closed:
# if gitleaks is missing or errors, the repo is skipped rather than pushed blind.
secret_gate() {
    local label="$1"
    local safe_label="${label//\//-}"
    local report="$LEAK_DIR/${safe_label}-$(date '+%Y-%m-%d').json"

    if [ ! -x "$GITLEAKS" ]; then
        log "[$label] BLOCKED: gitleaks not found at $GITLEAKS — not committing"
        git reset -q
        attention "$label" "gitleaks unavailable; staged changes were not committed"
        return 1
    fi

    local rc=0
    rm -f "$report"
    "$GITLEAKS" git --pre-commit --staged --redact --no-banner -l error \
        -f json -r "$report" . >> "$LOG" 2>&1 || rc=$?

    if [ "$rc" -eq 0 ]; then
        rm -f "$report"
        return 0
    fi

    git reset -q
    if [ "$rc" -eq 1 ] && [ -s "$report" ] && jq -e 'type == "array" and length > 0' "$report" > /dev/null 2>&1; then
        log "[$label] BLOCKED: gitleaks found possible secrets — nothing committed. Details (redacted): $report"
        attention "$label" "possible secret detected; see redacted report at $report"
        python3 - "$report" >> "$LOG" 2>&1 <<'PYEOF' || true
import json, sys
for f in json.load(open(sys.argv[1])):
    print(f"    {f['RuleID']:28} {f['File']}:{f['StartLine']}")
PYEOF
    else
        log "[$label] BLOCKED: gitleaks did not complete cleanly (exit $rc or invalid report) — nothing committed"
        attention "$label" "gitleaks failed or returned no valid report; staged changes were not committed"
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

    if [ "$push_mode" = "local" ]; then
        log "[$label] Kept commit local"
        return 0
    fi
    if [ "$push_mode" = "push-if-remote" ] && ! git remote get-url origin > /dev/null 2>&1; then
        log "[$label] No origin remote; committed locally only"
        return 0
    fi
    git push origin master >> "$LOG" 2>&1 && log "[$label] Pushed to GitHub" || log "[$label] WARNING: push failed"
}

# --- edq repo ---
cd /srv/containers/edq
git rev-parse --git-dir > /dev/null 2>&1 || { log "[edq] Not a git repo, skipping"; exit 0; }

if [ "${NIGHTLY_COMMIT_SCOPE:-all}" != "dragonsuite" ]; then
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
fi

# --- Dragonsuite application/source repositories ---
# Iterate the live registry so every Dashboard project path receives a
# clean-worktree
# checkpoint even when there is no upstream commit to pull. Commits stay local;
# the nightly task is a safety checkpoint, not a publish operation.
log "--- Dragonsuite project repos: nightly source checkpoints ---"
SERVICE_TSV=$(mktemp)
jq -r '.services[] | select(.project_path != null and .project_path != "") | [.id, .project_path] | @tsv' \
    /srv/containers/edq/config/dragonsuite.json > "$SERVICE_TSV"
declare -A SEEN_PROJECT_PATHS=()
while IFS=$'\t' read -r service_id project_path; do
    if [ ! -d "$project_path" ]; then
        log "[$service_id] Registered project path is missing: $project_path"
        attention "$service_id" "registered project path is missing: $project_path"
        continue
    fi
    repo_root=$(git -C "$project_path" rev-parse --show-toplevel 2>/dev/null) || {
        log "[$service_id] No Git repository at $project_path; skipped"
        attention "$service_id" "registered project path is not a Git repository"
        continue
    }
    case "$project_path/" in
        "$repo_root/"*) project_scope="${project_path#"$repo_root"/}" ;;
        *)
            log "[$service_id] Project path is outside its Git checkout; skipped"
            attention "$service_id" "registered project path is outside its Git checkout"
            continue
            ;;
    esac
    [ -n "$project_scope" ] || project_scope="."
    scope_key="$repo_root/$project_scope"
    if [ -n "${SEEN_PROJECT_PATHS[$scope_key]:-}" ]; then
        log "[$service_id] Project path already scanned as ${SEEN_PROJECT_PATHS[$scope_key]}"
        continue
    fi
    SEEN_PROJECT_PATHS[$scope_key]="$service_id"

    index_lock=$(git -C "$repo_root" rev-parse --path-format=absolute --git-path index.lock)
    if [ -e "$index_lock" ]; then
        log "[$service_id] Git index is locked; skipped"
        attention "$service_id" "Git index is locked; source changes remain uncommitted"
        continue
    fi
    if [ -n "$(git -C "$repo_root" ls-files -u)" ]; then
        log "[$service_id] Unresolved merge conflicts; skipped"
        attention "$service_id" "unresolved merge conflicts need review"
        continue
    fi
    if ! git -C "$repo_root" diff --cached --quiet -- . ":(exclude)$project_scope" ":(exclude)$project_scope/**"; then
        log "[$service_id] Unrelated changes are already staged in the shared checkout; skipped"
        attention "$service_id" "unrelated files are already staged in the shared Git checkout"
        continue
    fi
    if [ -z "$(git -C "$repo_root" status --porcelain --untracked-files=all -- "$project_scope")" ]; then
        log "[$service_id] Clean"
        continue
    fi
    if ! git -C "$repo_root" symbolic-ref -q HEAD >/dev/null; then
        log "[$service_id] Detached HEAD with pending changes; skipped"
        attention "$service_id" "repository has pending changes on a detached HEAD"
        continue
    fi

    git -C "$repo_root" add -u -- "$project_scope"
    UNTRACKED_TSV=$(mktemp)
    git -C "$repo_root" ls-files --others --exclude-standard -z -- "$project_scope" > "$UNTRACKED_TSV"
    while IFS= read -r -d '' candidate; do
        case "/$candidate/" in
            */node_modules/*|*/.venv/*|*/venv/*|*/__pycache__/*|*/models/*|*/checkpoints/*|*/cache/*|*/outputs/*|*/output/*|*/logs/*|*/dist/*|*/build/*|*/.next/*|*/.cache/*|*/workspaces/*|*/tmp/*|*/temp/*)
                log "[$service_id] Skipped runtime/generated path: $candidate"
                continue
                ;;
        esac
        if [ ! -f "$repo_root/$candidate" ] || [ -L "$repo_root/$candidate" ]; then
            log "[$service_id] Skipped non-regular untracked path: $candidate"
            attention "$service_id" "untracked non-regular path needs review: $candidate"
            continue
        fi
        candidate_size=$(stat -c '%s' "$repo_root/$candidate" 2>/dev/null || echo 0)
        if [ "$candidate_size" -gt 10485760 ]; then
            log "[$service_id] Skipped untracked file larger than 10 MiB: $candidate"
            attention "$service_id" "untracked file exceeds 10 MiB and needs review: $candidate"
            continue
        fi
        git -C "$repo_root" add -- "$candidate"
    done < "$UNTRACKED_TSV"
    rm -f "$UNTRACKED_TSV"

    cd "$repo_root"
    if git diff --cached --quiet; then
        log "[$service_id] No eligible source files to commit"
    else
        commit_staged "dragonsuite/$service_id" local
    fi
done < "$SERVICE_TSV"
rm -f "$SERVICE_TSV"

if [ -n "$ATTENTION_ROWS" ]; then
    {
        echo "# Nightly commit needs attention — $(date '+%Y-%m-%d')"
        echo
        echo "The scheduled checkpoint skipped these changes; review the details in nightly_commit.log."
        echo
        echo '| Project | Reason |'
        echo '|---|---|'
        printf '%b' "$ATTENTION_ROWS"
    } > "$ATTENTION_FILE"
    log "Wrote $ATTENTION_FILE"
else
    rm -f "$ATTENTION_FILE"
fi
