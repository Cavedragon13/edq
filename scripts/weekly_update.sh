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

mkdir -p "$PROJECT_DIR/logs"

# Per-line timestamps (a single run spans many minutes). This function is the
# only writer to LOG_FILE — cron must redirect stdout elsewhere
# (logs/weekly_update_cron.log), otherwise every line lands twice.
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
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

report_repo_status() {
    local repo_dir="$1" repo_name="$2" pull_hint="$3"
    if git -C "$repo_dir" fetch --quiet 2>/dev/null; then
        local behind current_sha
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
            PENDING_ROWS+="| $repo_name | \`$current_sha\` | **$behind commit(s) available** | $pull_hint |\n"
        fi
    else
        log "  ⚠️  $repo_name — fetch failed (no remote or network issue)"
        PENDING_ROWS+="| $repo_name | unknown | fetch failed | check network/remote |\n"
    fi
}

for repo_dir in "$PROJECT_DIR/projects"/*/; do
    [ -d "$repo_dir/.git" ] || continue
    repo_name=$(basename "$repo_dir")
    report_repo_status "$repo_dir" "$repo_name" "\`git pull\` in projects/$repo_name"
done

# Vendored/embedded source repos that live outside projects/*/ and are not
# safe to auto-pull-and-relaunch via the Dragonsuite pass below (they need a
# bespoke compile step, e.g. a CMake/CUDA rebuild, that the generic
# requirements.txt-sync-and-relaunch flow doesn't know how to do). Report
# only, same as the scan above, so drift is visible in the scorecard instead
# of silently going unnoticed.
declare -A EXTRA_REPOS=(
    ["krea2-stable-diffusion-cpp"]="$PROJECT_DIR/krea2/src/stable-diffusion.cpp"
)
for repo_name in "${!EXTRA_REPOS[@]}"; do
    repo_dir="${EXTRA_REPOS[$repo_name]}"
    [ -d "$repo_dir/.git" ] || continue
    report_repo_status "$repo_dir" "$repo_name" "manual rebuild — see krea2/src/stable-diffusion.cpp (git pull + submodule update + cmake --build build-cuda)"
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

# comfy-cli owns the ComfyUI checkout (a detached release tag, not a branch),
# so it is updated with comfy-cli rather than git pull. VIRTUAL_ENV/PATH are
# pinned explicitly: an inherited VIRTUAL_ENV once pointed comfy-cli's installs
# at another service's venv (docs/venvs.md, 2026-08-23).
comfy_update() {  # $1 = latest | a version number such as 0.37.2
    env VIRTUAL_ENV="$PROJECT_DIR/venv_comfyui" PATH="$PROJECT_DIR/venv_comfyui/bin:/usr/bin:/bin" \
        "$PROJECT_DIR/venv_comfyui/bin/comfy" --workspace "$PROJECT_DIR/projects/ComfyUI" --skip-prompt \
        update comfy --version "$1" < /dev/null   # never eat the loop's service rows
}

# Launch-verify an updated service (uses the loop's svc_*/pre_sha/new_sha/
# dep_note). On failure roll back: comfy-cli to $rollback_tag when set
# (restores its requirements too), otherwise git reset to $pre_sha.
# GPU (one-shot) services get stopped again after a successful check;
# persistent services (no vram_gb, e.g. Odysseus) are left running.
launch_verify() {
    # Kept on disk (not a deleted mktemp) so the attention note can point at it.
    local verify_log="$PROJECT_DIR/logs/weekly_verify_${svc_id}.log"
    local launch_rc=1
    if [ -n "$launch_cmd" ]; then
        timeout 300 bash -c "$launch_cmd" > "$verify_log" 2>&1 < /dev/null
        launch_rc=$?
    fi

    if [ "$launch_rc" -eq 0 ] && grep -qi "ready at\|already running" "$verify_log"; then
        log "  ✅ $svc_name — updated $pre_sha -> $new_sha, launch-verified ($dep_note)"
        UPDATED_ROWS+="| $svc_name | \`${pre_sha:0:7}\` -> \`$new_sha\` | $dep_note |\n"
        if [ "$svc_kind" = "gpu" ] && [ -n "$stop_cmd" ]; then
            bash -c "$stop_cmd" >/dev/null 2>&1 || true
        fi
        return
    fi

    tail -15 "$verify_log" | while IFS= read -r l; do log "       $l"; done
    bash -c "$stop_cmd" >/dev/null 2>&1 || true
    if [ -n "$rollback_tag" ] && comfy_update "$rollback_tag" >> "$PROJECT_DIR/logs/weekly_comfy_update.log" 2>&1; then
        log "  ❌ $svc_name — launch-verify FAILED after update, rolled back to v$rollback_tag with comfy-cli"
        ATTENTION_ROWS+="| $svc_name | launch-verify failed, rolled back to v$rollback_tag | see logs/weekly_verify_${svc_id}.log |\n"
    else
        log "  ❌ $svc_name — launch-verify FAILED after update, rolling back code to $pre_sha"
        log "     ($dep_note — dependency changes are NOT auto-rolled-back; check the venv if this recurs)"
        git -C "$project_path" reset --hard "$pre_sha" -q
        ATTENTION_ROWS+="| $svc_name | launch-verify failed, code rolled back to \`${pre_sha:0:7}\` | $dep_note — see logs/weekly_verify_${svc_id}.log |\n"
    fi
}

while IFS=$'\t' read -r svc_id svc_name project_path port launch_cmd stop_cmd svc_kind; do
    [ -d "$project_path/.git" ] || continue
    rollback_tag=""

    if ! git -C "$project_path" fetch --quiet 2>/dev/null; then
        log "  ⚠️  $svc_name — fetch failed, skipping"
        ATTENTION_ROWS+="| $svc_name | fetch failed | check network/remote |\n"
        continue
    fi

    # Pinned checkouts (detached HEAD) have no tracking branch. ComfyUI is
    # rolled forward to the newest stable tag with comfy-cli; any other pinned
    # checkout is left alone on purpose.
    upstream_ref=$(git -C "$project_path" rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || true)
    if [ -z "$upstream_ref" ]; then
        if [ "$svc_id" != "comfyui" ]; then
            log "  ⏭️  $svc_name — pinned checkout (detached HEAD / no tracking branch), not auto-updated"
            continue
        fi
        git -C "$project_path" fetch --tags --quiet 2>/dev/null || true
        pre_sha=$(git -C "$project_path" rev-parse --short HEAD)
        pre_tag=$(git -C "$project_path" describe --tags --exact-match 2>/dev/null || true)
        latest_tag=$(git -C "$project_path" tag --list 'v[0-9]*' --sort=-v:refname | grep -v -- '-' | head -1)   # stable only, like --version latest
        if [ -z "$latest_tag" ] || [ "$pre_tag" = "$latest_tag" ]; then
            continue
        fi
        log "  🔄 $svc_name — ${pre_tag:-$pre_sha} -> $latest_tag via comfy-cli"
        bash -c "$stop_cmd" >/dev/null 2>&1 || true   # verify the new code, not a still-running old process
        if ! comfy_update latest > "$PROJECT_DIR/logs/weekly_comfy_update.log" 2>&1; then
            log "  ⚠️  $svc_name — comfy-cli update failed, left at ${pre_tag:-$pre_sha}"
            ATTENTION_ROWS+="| $svc_name | comfy-cli update to $latest_tag failed | see logs/weekly_comfy_update.log |\n"
            continue
        fi
        new_sha="$(git -C "$project_path" rev-parse --short HEAD) ($latest_tag)"
        dep_note="comfy-cli update (requirements reinstalled, torch untouched); custom nodes not updated"
        rollback_tag="${pre_tag#v}"
        launch_verify
        continue
    fi

    behind=$(git -C "$project_path" rev-list "HEAD..$upstream_ref" --count 2>/dev/null || echo "?")
    if [ "$behind" = "0" ] || [ "$behind" = "?" ]; then
        continue
    fi

    pre_sha=$(git -C "$project_path" rev-parse HEAD)
    dirty=""
    [ -n "$(git -C "$project_path" status --porcelain --untracked-files=no 2>/dev/null)" ] && dirty=1

    pull_ok=1
    stashed=""
    if [ -n "$dirty" ]; then
        git -C "$project_path" stash push -q -m "weekly_update.sh auto-stash $DATE" || pull_ok=0
        stashed=1
    fi

    # Local patch commits (earlier auto-merges, manual fixes) make a plain
    # --ff-only pull impossible forever after, so replay them on top of the
    # new upstream instead. A rebase conflict is left for a human.
    local_ahead=$(git -C "$project_path" rev-list --count "$upstream_ref..HEAD" 2>/dev/null || echo "0")
    if [ "$pull_ok" = "1" ]; then
        if [ "$local_ahead" = "0" ]; then
            git -C "$project_path" pull --ff-only --quiet 2>/dev/null || pull_ok=0
        elif ! git -C "$project_path" rebase --quiet "$upstream_ref" >/dev/null 2>&1; then
            git -C "$project_path" rebase --abort >/dev/null 2>&1 || true
            git -C "$project_path" reset --hard "$pre_sha" -q
            [ -n "$stashed" ] && git -C "$project_path" stash pop -q 2>/dev/null
            log "  ⚠️  $svc_name — $local_ahead local patch commit(s) conflict with upstream, needs manual rebase (left untouched)"
            ATTENTION_ROWS+="| $svc_name | local patch commits conflict with upstream | manual rebase onto $upstream_ref — see projects/$(basename "$project_path") |\n"
            continue
        fi
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
            # Tracked files only (-u): `add -A` once swept an untracked
            # venv into the ai-toolkit repo.
            if [ -n "$(git -C "$project_path" status --porcelain --untracked-files=no 2>/dev/null)" ]; then
                git -C "$project_path" add -u
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
            venv_python="$PROJECT_DIR/$venv_name/bin/python3"
            sync_out=$(source "$PROJECT_DIR/$venv_name/bin/activate" 2>/dev/null && pip install -r "$project_path/requirements.txt" --upgrade 2>&1)
            sync_rc=$?
            mismatch_out=$("$venv_python" "$SCRIPT_DIR/verify_pip_sync.py" "$project_path/requirements.txt" "$venv_python" 2>&1)
            if [ -n "$mismatch_out" ]; then
                # pip can exit 0 while an exact pin still didn't converge on
                # the first resolver pass (see verify_pip_sync.py docstring).
                # A second identical install call has reliably fixed this.
                log "     pip sync did not converge on first pass, retrying:"
                echo "$mismatch_out" | while IFS= read -r l; do log "       $l"; done
                sync_out=$(source "$PROJECT_DIR/$venv_name/bin/activate" 2>/dev/null && pip install -r "$project_path/requirements.txt" --upgrade 2>&1)
                sync_rc=$?
                mismatch_out=$("$venv_python" "$SCRIPT_DIR/verify_pip_sync.py" "$project_path/requirements.txt" "$venv_python" 2>&1)
            fi
            if [ "$sync_rc" -eq 0 ] && [ -z "$mismatch_out" ]; then
                dep_note="requirements.txt synced in $venv_name (pins verified)"
            else
                dep_note="requirements.txt changed but pip sync FAILED to converge in $venv_name — check manually"
                log "     pip sync error tail:"
                echo "$sync_out" | tail -10 | while IFS= read -r l; do log "       $l"; done
            fi
        else
            dep_note="requirements.txt changed but no venv could be inferred — sync manually"
        fi
    fi

    launch_verify
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
    ["zimage"]="$PROJECT_DIR/venv_zimage"
    ["qwen_image_layered"]="$PROJECT_DIR/venv_qwen_image_layered"
    ["deepgen"]="$PROJECT_DIR/venv_deepgen"
    ["hidream_o1"]="$PROJECT_DIR/venv_hidream_o1"
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
log "--- Flagging attention items for the next Claude Code session ---"

# Age each attention item. The flag file is rewritten every week, so without
# this a problem that recurs for months reads like a fresh one-week warning
# (OmniVoice Studio sat 5 weeks this way, 2026-08-23 → 09-20). First-seen
# dates persist in weekly_update_stuck.json; resolved items drop out.
if [ -n "$ATTENTION_ROWS" ]; then
    ATTENTION_ROWS=$(ATTENTION_ROWS="$ATTENTION_ROWS" DATE="$DATE" STATE="$PROJECT_DIR/logs/weekly_update_stuck.json" python3 - <<'PYEOF'
import datetime
import json
import os

state_path, today = os.environ["STATE"], os.environ["DATE"]
try:
    with open(state_path) as fh:
        state = json.load(fh)
except (OSError, ValueError):
    state = {}
out, seen = [], {}
for row in os.environ["ATTENTION_ROWS"].replace("\\n", "\n").split("\n"):
    cells = row.split("|")
    if len(cells) < 4:
        continue
    name = cells[1].strip()
    first = state.get(name, today)
    seen[name] = first
    weeks = (datetime.date.fromisoformat(today) - datetime.date.fromisoformat(first)).days // 7
    if weeks >= 1:
        tag = f" — STUCK since {first} ({weeks} wk)" if weeks >= 2 else f" — since {first}"
        cells[2] = cells[2].rstrip() + tag + " "
    out.append("|".join(cells))
with open(state_path, "w") as fh:
    json.dump(seen, fh, indent=2)
print("\\n".join(out) + "\\n", end="")
PYEOF
)
else
    rm -f "$PROJECT_DIR/logs/weekly_update_stuck.json"
fi

ATTENTION_FLAG="$PROJECT_DIR/logs/weekly_update_attention.md"
if [ -n "$ATTENTION_ROWS" ]; then
    {
        echo "# Weekly update needs a decision — $DATE"
        echo ""
        echo "Auto-generated by weekly_update.sh. Delete this file once handled,"
        echo "or it clears itself automatically once these items resolve."
        echo ""
        printf '%b' "$ATTENTION_ROWS" | sed 's/^/- /'
    } > "$ATTENTION_FLAG"
    log "  🔔 wrote $ATTENTION_FLAG — next session should surface this"
else
    if [ -f "$ATTENTION_FLAG" ]; then
        rm -f "$ATTENTION_FLAG"
        log "  ✅ previous attention items resolved — flag file cleared"
    else
        log "  ✅ nothing needs attention — no flag file"
    fi
fi

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
