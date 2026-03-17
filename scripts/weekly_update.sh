#!/bin/bash
# Weekly stack update check — runs every Sunday 03:30
# Checks for available git updates and logs outdated pip packages
# Does NOT auto-pull or auto-upgrade (avoids silent breakage)
# Log: /srv/containers/edq/logs/weekly_update.log

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$PROJECT_DIR/logs/weekly_update.log"
SCORECARD="$HOME/knowledge-base/Dragonsuite/service-versions.md"
DATE=$(date '+%Y-%m-%d')
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

mkdir -p "$PROJECT_DIR/logs"

log() {
    echo "[$TIMESTAMP] $*" | tee -a "$LOG_FILE"
}

log "======================================================"
log "Weekly stack update check — $DATE"
log "======================================================"

# -------------------------------------------------------
# 1. Check git repos for available upstream updates
# -------------------------------------------------------
log ""
log "--- Git repos: checking for upstream updates ---"

shopt -s nullglob

# Accumulate rows for the Pending Updates scorecard section
PENDING_ROWS=""

for repo_dir in "$PROJECT_DIR/projects"/*/; do
    if [ ! -d "$repo_dir/.git" ]; then
        continue
    fi

    repo_name=$(basename "$repo_dir")

    # Fetch without pulling
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
# 2. Check key venvs for outdated packages (log only)
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

    # Run in subshell to isolate venv activation; || true prevents set -e from exiting on pip errors
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
# 3. Update Obsidian scorecard — Pending Updates section
# -------------------------------------------------------
log ""
log "--- Updating Obsidian scorecard pending updates ---"

if [ -f "$SCORECARD" ] && [ -n "$PENDING_ROWS" ]; then
    python3 - <<PYEOF
import re

scorecard_path = "$SCORECARD"
date = "$DATE"
rows = "$PENDING_ROWS"

with open(scorecard_path, 'r') as f:
    content = f.read()

header = "| Repo | Current SHA | Behind | Action |\n|---|---|---|---|\n"
table = header + rows.replace('\\n', '\n').rstrip('\n') + '\n'
new_section = f"## Pending Updates\n\nLast checked: {date}\n\n{table}"

# Replace existing Pending Updates section (between the heading and the next ---)
content = re.sub(
    r'## Pending Updates\n.*?(?=\n---)',
    new_section,
    content,
    flags=re.DOTALL
)

with open(scorecard_path, 'w') as f:
    f.write(content)

print("Scorecard pending updates written.")
PYEOF
    log "  ✅ Pending updates section updated"
else
    log "  ⚠️  Scorecard not found or no git data — skipping pending updates"
fi

# -------------------------------------------------------
# 4. Update Obsidian version scorecard git SHAs
# -------------------------------------------------------
log ""
log "--- Updating Obsidian scorecard git SHAs ---"

if [ -f "$SCORECARD" ]; then
    declare -A TRACKED_REPOS=(
        ["Fish Speech"]="$PROJECT_DIR/projects/fish-speech"
        ["MatAnyone 2"]="$PROJECT_DIR/projects/matanyone2"
        ["ACE-Step 1.5"]="$PROJECT_DIR/projects/ACE-Step-1.5"
        ["LivePortrait"]="$PROJECT_DIR/projects/LivePortrait"
        ["Wan2GP"]="$PROJECT_DIR/projects/Wan2GP"
        ["SAM 2.1"]="$PROJECT_DIR/projects/sam2"
        ["FaceFusion"]="$PROJECT_DIR/projects/facefusion"
        ["HeartMuLa"]="$PROJECT_DIR/projects/heartmula"
        ["Hunyuan3D-2"]="$PROJECT_DIR/projects/hunyuan3d"
    )

    for service in "${!TRACKED_REPOS[@]}"; do
        repo="${TRACKED_REPOS[$service]}"
        if [ -d "$repo/.git" ]; then
            sha=$(git -C "$repo" rev-parse --short HEAD 2>/dev/null || echo "unknown")
            # Update the SHA column in the scorecard table (sed in-place)
            # Matches: | Service Name | port | old_sha | ...
            sed -i "s/| $service | \([0-9]*\) | [a-f0-9]* /| $service | \1 | $sha /" "$SCORECARD" 2>/dev/null || true
        fi
    done

    # Update "Last Checked" date in the scorecard header
    sed -i "s/Last checked: [0-9-]*/Last checked: $DATE/" "$SCORECARD" 2>/dev/null || true
    log "  ✅ Scorecard updated at $SCORECARD"
else
    log "  ⚠️  Scorecard not found at $SCORECARD — skipping SHA update"
fi

log ""
log "--- Weekly check complete ---"
log ""
