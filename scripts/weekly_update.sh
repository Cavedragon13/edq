#!/bin/bash
# Weekly stack update — runs every Sunday 03:30
#
# Two passes:
#   1. Full repo scan (unchanged from before): fetch + report only, for
#      every git repo under projects/*/. Feeds the "Pending Updates" table
#      so nothing outside Dragonsuite gets touched automatically.
#   2. Dragonsuite auto-update: for services actually listed in
#      dragonsuite.json (i.e. the AI stack, not personal/business side
#      projects), auto-pull, best-effort dependency sync, and launch-verify
#      each one. Failures roll the git pull back (git reset --hard) rather
#      than leaving a broken service; anything this script can't safely
#      resolve on its own (a real merge conflict, an unrecognized dependency
#      setup) is skipped and flagged in "Needs Attention", never guessed at.
#
# Log: /srv/containers/edq/logs/weekly_update.log
# Scorecard: ~/knowledge-base/Dragonsuite/service-versions.md

set -uo pipefail   # no -e: one repo/service failing must not kill the run

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$PROJECT_DIR/logs/weekly_update.log"
SCORECARD="$HOME/knowledge-base/Dragonsuite/service-versions.md"
DRAGONSUITE_JSON="$PROJECT_DIR/config/dragonsuite.json"
DATE=$(date '+%Y-%m-%d')
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

mkdir -p "$PROJECT_DIR/logs"

log() {
    echo "[$TIMESTAMP] $*" | tee -a "$LOG_FILE"
}

log "======================================================"
log "Weekly stack update — $DATE"
log "======================================================"

# -------------------------------------------------------
# 0. Point origin/HEAD at the real default branch for every repo first.
#    Repos cloned without this set (common with some clone tools) make
#    `git rev-list HEAD..origin/HEAD` fail with "ambiguous argument",
#    which previously showed up as a false "fetch failed / unknown" in
#    the scorecard even though the repo was perfectly reachable.
# -------------------------------------------------------
shopt -s nullglob
for repo_dir in "$PROJECT_DIR/projects"/*/; do
    [ -d "$repo_dir/.git" ] || continue
    git -C "$repo_dir" remote set-head origin -a >/dev/null 2>&1 || true
done

# -------------------------------------------------------
# 1. Full repo scan: fetch + report only (all of projects/*/)
# -------------------------------------------------------
log ""
log "--- Git repos: checking for upstream updates ---"

PENDING_ROWS=""

for repo_dir in "$PROJECT_DIR/projects"/*/; do
    if [ ! -d "$repo_dir/.git" ]; then
        continue
    fi

    repo_name=$(basename "$repo_dir")

    if git -C "$repo_dir" fetch --quiet 2>/dev/null; then
        behind=$(git -C "$repo_dir" rev-list HEAD..origin/HEAD --count 2>/dev/null || echo "?")
        current_sha=$(git -C "$repo_dir" rev-parse --short HEAD 2>/dev/null || echo "unknown")

        if [ "$behind" = "0" ]; then
            log "  ✅ $repo_name — up to date ($current_sha)"
            PENDING_ROWS+="| $repo_name | \`$current_sha\` | up to date | — |\n"
        elif [ "$behind" = "?" ]; then
            log "  ⚠️  $repo_name — could not determine update status"
            PENDING_ROWS+="| $repo_name | \`$current_sha\` | unknown | check manually |\n"
        else
            log "  🔄 $repo_name — $behind commit(s) available (current: $current_sha)"
            PENDING_ROWS+="| $repo_name | \`$current_sha\` | **$behind commit(s) available** | \`git pull\` in projects/$repo_name |\n"
        fi
    else
        log "  ⚠️  $repo_name — fetch failed (no remote or network issue)"
        PENDING_ROWS+="| $repo_name | unknown | fetch failed | check network/remote |\n"
    fi
done

# -------------------------------------------------------
# 2. Dragonsuite auto-update: pull + sync deps + launch-verify, scoped to
#    services actually declared in dragonsuite.json.
# -------------------------------------------------------
log ""
log "--- Dragonsuite services: auto-update + launch-verify ---"

UPDATED_ROWS=""
ATTENTION_ROWS=""

SERVICES_TSV=$(mktemp)
DRAGONSUITE_JSON="$DRAGONSUITE_JSON" python3 - > "$SERVICES_TSV" <<'PYEOF'
import json
import os

with open(os.environ["DRAGONSUITE_JSON"]) as f:
    data = json.load(f)

services = data["services"] if isinstance(data, dict) and "services" in data else data

for svc in services:
    if not isinstance(svc, dict):
        continue
    pp = svc.get("project_path")
    if not pp:
        continue
    row = [
        svc.get("id", ""),
        svc.get("name", ""),
        pp,
        str(svc.get("port", "")),
        (svc.get("launch_command") or "").replace("\t", " "),
        (svc.get("stop_command") or "").replace("\t", " "),
        "gpu" if "vram_gb" in svc else "persistent",
    ]
    print("\t".join(row))
PYEOF

while IFS=$'\t' read -r svc_id svc_name project_path port launch_cmd stop_cmd svc_kind; do
    [ -d "$project_path/.git" ] || continue

    if ! git -C "$project_path" fetch --quiet 2>/dev/null; then
        log "  ⚠️  $svc_name — fetch failed, skipping"
        ATTENTION_ROWS+="| $svc_name | fetch failed | check network/remote |\n"
        continue
    fi

    behind=$(git -C "$project_path" rev-list HEAD..origin/HEAD --count 2>/dev/null || echo "?")
    if [ "$behind" = "0" ] || [ "$behind" = "?" ]; then
        continue
    fi

    pre_sha=$(git -C "$project_path" rev-parse HEAD)
    dirty=""
    [ -n "$(git -C "$project_path" status --porcelain 2>/dev/null)" ] && dirty=1

    pull_ok=1
    stashed=""
    if [ -n "$dirty" ]; then
        git -C "$project_path" stash push -q -m "weekly_update.sh auto-stash $DATE" || pull_ok=0
        stashed=1
    fi

    if [ "$pull_ok" = "1" ]; then
        git -C "$project_path" pull --ff-only --quiet 2>/dev/null || pull_ok=0
    fi

    if [ "$pull_ok" = "1" ] && [ -n "$stashed" ]; then
        pop_output=$(git -C "$project_path" stash pop 2>&1)
        if echo "$pop_output" | grep -q "CONFLICT"; then
            # Can't safely auto-resolve a real conflict — undo the pull
            # entirely and restore the original local patches untouched.
            git -C "$project_path" merge --abort >/dev/null 2>&1 || true
            git -C "$project_path" checkout -- . >/dev/null 2>&1 || true
            git -C "$project_path" reset --hard "$pre_sha" -q
            git -C "$project_path" stash pop -q 2>/dev/null || true
            log "  ⚠️  $svc_name — local patches conflict with upstream, needs manual review (left untouched)"
            ATTENTION_ROWS+="| $svc_name | merge conflict with local patches | manual review — see projects/$(basename "$project_path") |\n"
            continue
        else
            # Clean merge of local patches onto the new upstream commit —
            # commit them so next week's run starts from a clean tree.
            if [ -n "$(git -C "$project_path" status --porcelain 2>/dev/null)" ]; then
                git -C "$project_path" add -A
                git -C "$project_path" commit -q -m "Auto-merge local patches after weekly update ($DATE)"
            fi
        fi
    fi

    if [ "$pull_ok" != "1" ]; then
        log "  ⚠️  $svc_name — pull failed, skipping (left at $pre_sha)"
        ATTENTION_ROWS+="| $svc_name | pull failed | check manually — projects/$(basename "$project_path") |\n"
        continue
    fi

    new_sha=$(git -C "$project_path" rev-parse --short HEAD)

    # Best-effort dependency sync: only for the well-understood
    # requirements.txt + venv pattern. Anything else (uv/pyproject-only,
    # a custom installer script like FaceFusion's install.py, Docker
    # image rebuilds) is a per-project judgment call this script does not
    # attempt — those get flagged, not guessed at.
    dep_note="code only (no requirements.txt change, or unrecognized dep setup — sync manually if needed)"
    if git -C "$project_path" diff --name-only "$pre_sha" HEAD 2>/dev/null | grep -qx "requirements.txt"; then
        venv_name=""
        if [ -n "$launch_cmd" ]; then
            script_path=$(echo "$launch_cmd" | grep -oP '(?<=bash )scripts/\S+\.sh')
            [ -n "$script_path" ] && venv_name=$(grep -oP '(?<=^VENV=")[^"]+' "$PROJECT_DIR/$script_path" 2>/dev/null | head -1)
        fi
        if [ -n "$venv_name" ] && [ -d "$PROJECT_DIR/$venv_name" ]; then
            sync_out=$(source "$PROJECT_DIR/$venv_name/bin/activate" 2>/dev/null && pip install -r "$project_path/requirements.txt" --upgrade 2>&1)
            sync_rc=$?
            if [ "$sync_rc" -eq 0 ]; then
                dep_note="requirements.txt synced in $venv_name"
            else
                dep_note="requirements.txt changed but pip sync FAILED in $venv_name — check manually"
                log "     pip sync error tail:"
                echo "$sync_out" | tail -10 | while IFS= read -r l; do log "       $l"; done
            fi
        else
            dep_note="requirements.txt changed but no venv could be inferred — sync manually"
        fi
    fi

    # Launch-verify. GPU (one-shot) services get stopped again after a
    # successful check; persistent services (no vram_gb, e.g. Odysseus)
    # are left running.
    verify_log=$(mktemp)
    if [ -n "$launch_cmd" ]; then
        timeout 300 bash -c "$launch_cmd" > "$verify_log" 2>&1
        launch_rc=$?
    else
        launch_rc=1
    fi

    if [ "$launch_rc" -eq 0 ] && grep -qi "ready at\|already running" "$verify_log"; then
        log "  ✅ $svc_name — updated $pre_sha -> $new_sha, launch-verified ($dep_note)"
        UPDATED_ROWS+="| $svc_name | \`${pre_sha:0:7}\` -> \`$new_sha\` | $dep_note |\n"
        if [ "$svc_kind" = "gpu" ] && [ -n "$stop_cmd" ]; then
            bash -c "$stop_cmd" >/dev/null 2>&1 || true
        fi
    else
        log "  ❌ $svc_name — launch-verify FAILED after update, rolling back code to $pre_sha"
        log "     ($dep_note — dependency changes are NOT auto-rolled-back; check the venv if this recurs)"
        tail -15 "$verify_log" | while IFS= read -r l; do log "       $l"; done
        bash -c "$stop_cmd" >/dev/null 2>&1 || true
        git -C "$project_path" reset --hard "$pre_sha" -q
        ATTENTION_ROWS+="| $svc_name | launch-verify failed, code rolled back to \`${pre_sha:0:7}\` | $dep_note — check /tmp for this service's log |\n"
    fi
    rm -f "$verify_log"
done < "$SERVICES_TSV"
rm -f "$SERVICES_TSV"

# -------------------------------------------------------
# 3. Pip outdated packages (log only, unchanged from before)
# -------------------------------------------------------
log ""
log "--- Pip outdated packages (log only, no auto-upgrade) ---"

declare -A VENVS=(
    ["fish_speech"]="$PROJECT_DIR/venv_fish_speech"
    ["tada"]="$PROJECT_DIR/venv_tada"
    ["matanyone2"]="$PROJECT_DIR/venv_matanyone2"
    ["flux2"]="$PROJECT_DIR/venv_flux2"
    ["dragonsuite"]="$PROJECT_DIR/venv_dragonsuite"
    ["wan_1b"]="$PROJECT_DIR/venv_wan_1b"
    ["ltxvideo"]="$PROJECT_DIR/venv_ltxvideo"
    ["qwen3_tts"]="$PROJECT_DIR/venv_qwen3_tts"
)

for venv_name in "${!VENVS[@]}"; do
    venv_path="${VENVS[$venv_name]}"
    if [ ! -d "$venv_path" ]; then
        continue
    fi

    outdated_output=$(
        source "$venv_path/bin/activate" 2>/dev/null
        pip list --outdated --format=columns 2>/dev/null | tail -n +3
    ) || true

    count=$(echo "$outdated_output" | grep -c . || true)
    if [ "$count" -eq 0 ]; then
        log "  ✅ venv_$venv_name — all packages up to date"
    else
        log "  🔄 venv_$venv_name — $count outdated package(s)"
        echo "$outdated_output" | while IFS= read -r line; do
            [ -n "$line" ] && log "       $line"
        done
    fi
done

# -------------------------------------------------------
# 4. Update Obsidian scorecard: Auto-Updated / Needs Attention / Pending
# -------------------------------------------------------
log ""
log "--- Updating Obsidian scorecard ---"

if [ -f "$SCORECARD" ]; then
    DATE="$DATE" UPDATED_ROWS="$UPDATED_ROWS" ATTENTION_ROWS="$ATTENTION_ROWS" PENDING_ROWS="$PENDING_ROWS" SCORECARD="$SCORECARD" python3 - <<'PYEOF'
import os
import re

scorecard_path = os.environ["SCORECARD"]
date = os.environ["DATE"]

def table(header, rows):
    rows = rows.replace('\\n', '\n').rstrip('\n')
    if not rows:
        rows = "| — | — | — |" if header.count('|') == 4 else "| — | — | — | — |"
    return header + rows + '\n'

updated_section = "## Auto-Updated This Run\n\nLast run: %s\n\n%s" % (
    date, table("| Service | SHA | Notes |\n|---|---|---|\n", os.environ["UPDATED_ROWS"])
)
attention_section = "## Needs Attention\n\nLast run: %s\n\n%s" % (
    date, table("| Service | Issue | Action |\n|---|---|---|\n", os.environ["ATTENTION_ROWS"])
)
pending_section = "## Pending Updates\n\nLast checked: %s\n\n%s" % (
    date, table("| Repo | Current SHA | Behind | Action |\n|---|---|---|---|\n", os.environ["PENDING_ROWS"])
)

with open(scorecard_path, 'r') as f:
    content = f.read()

if "## Auto-Updated This Run" in content:
    content = re.sub(r"## Auto-Updated This Run\n.*?(?=\n---|\n## )", updated_section, content, flags=re.DOTALL)
else:
    content = updated_section + "\n---\n\n" + content

if "## Needs Attention" in content:
    content = re.sub(r"## Needs Attention\n.*?(?=\n---|\n## )", attention_section, content, flags=re.DOTALL)
else:
    content = content.replace(updated_section, updated_section + "\n---\n\n" + attention_section + "\n", 1)

content = re.sub(r"## Pending Updates\n.*?(?=\n---)", pending_section, content, flags=re.DOTALL)

with open(scorecard_path, 'w') as f:
    f.write(content)

print("Scorecard updated: Auto-Updated / Needs Attention / Pending Updates")
PYEOF
    log "  ✅ Scorecard updated at $SCORECARD"
else
    log "  ⚠️  Scorecard not found at $SCORECARD — skipping"
fi

log ""
log "--- Weekly update complete ---"
log ""
