#!/bin/bash
# process_publish_queue.sh
# Watches /srv/containers/edq/Publish/ for ZIP files, extracts them into
# the Seed13_Prod_Main repo, then commits and pushes to trigger Hostinger deploy.
#
# ZIP structure expected (Dragonart Studio output):
#   index.html
#   session_log.txt    (optional)
#   images/            (before/after PNGs)
#
# The ZIP filename becomes the gallery subdirectory name.
# Run by cron before the nightly commit (e.g. 01:50 daily).
#
# Usage: bash scripts/process_publish_queue.sh
#        bash scripts/process_publish_queue.sh --dry-run

set -e

PUBLISH_DIR="/srv/containers/edq/Publish"
REPO_DIR="/srv/containers/edq/projects/Seed13_Prod_Main"
PROCESSED_DIR="$PUBLISH_DIR/.processed"
LOG_FILE="/srv/containers/edq/Publish/.publish_log.txt"
DRY_RUN=false

[[ "$1" == "--dry-run" ]] && DRY_RUN=true

mkdir -p "$PROCESSED_DIR"
cd "$REPO_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log "=== Publish queue check ==="

# Find all ZIPs in Publish dir (not in .processed)
ZIPS=("$PUBLISH_DIR"/*.zip)
if [[ ! -e "${ZIPS[0]}" ]]; then
    log "No ZIP files found. Nothing to do."
    exit 0
fi

COMMITTED=0

for zip in "${ZIPS[@]}"; do
    [[ -f "$zip" ]] || continue

    # Derive gallery slug from filename: strip path and .zip
    filename=$(basename "$zip")
    slug="${filename%.zip}"
    # Sanitize: lowercase, replace spaces with dashes
    slug=$(echo "$slug" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr '_' '-')

    log "Processing: $filename → galleries/$slug/"

    if $DRY_RUN; then
        log "  DRY RUN: would extract to $REPO_DIR/galleries/$slug/"
        continue
    fi

    # Create target directory in repo
    target="$REPO_DIR/galleries/$slug"
    mkdir -p "$target"

    # Extract ZIP to temp dir first to inspect
    tmpdir=$(mktemp -d)
    trap "rm -rf $tmpdir" EXIT

    if ! unzip -q "$zip" -d "$tmpdir"; then
        log "  ERROR: Failed to extract $zip — skipping"
        rm -rf "$tmpdir"
        trap - EXIT
        continue
    fi

    # Detect structure: some ZIPs may have a single subfolder
    # If root contains only one directory, descend into it
    top_contents=("$tmpdir"/*)
    if [[ ${#top_contents[@]} -eq 1 ]] && [[ -d "${top_contents[0]}" ]]; then
        tmpdir="${top_contents[0]}"
    fi

    # Copy contents to repo target
    cp -r "$tmpdir"/. "$target/"

    # Update index.html title and back-link if present
    if [[ -f "$target/index.html" ]]; then
        # Add a back-to-home link if not present
        if ! grep -q "seed13productions.com\|index.html\|Back to" "$target/index.html" 2>/dev/null; then
            # Inject a minimal back link before </body>
            sed -i 's|</body>|<div style="text-align:center;padding:2rem;font-family:sans-serif;"><a href="/" style="color:#C8571A;text-decoration:none;font-size:0.85rem;letter-spacing:0.1em;text-transform:uppercase;">&#8592; Seed 13 Productions</a></div>\n</body>|' "$target/index.html"
        fi
    fi

    # Clean up session log (optional — keep as readme)
    if [[ -f "$target/session_log.txt" ]]; then
        mv "$target/session_log.txt" "$target/README.txt"
    fi

    # Stage the new gallery files
    git -C "$REPO_DIR" add "galleries/$slug/"

    COMMITTED=$((COMMITTED + 1))
    log "  Added to repo: galleries/$slug/ ($(find "$target" -type f | wc -l) files)"

    # Move ZIP to processed
    mv "$zip" "$PROCESSED_DIR/${filename%.zip}_$(date '+%Y%m%d_%H%M%S').zip"

    rm -rf "$tmpdir"
    trap - EXIT
done

if [[ $COMMITTED -gt 0 ]] && ! $DRY_RUN; then
    log "Committing $COMMITTED new gallery/galleries..."
    git -C "$REPO_DIR" commit -m "publish: add $COMMITTED gallery/galleries from Publish queue

Auto-processed by process_publish_queue.sh on $(date '+%Y-%m-%d')
Co-Authored-By: Cavedragon13 <cavedragon13@gmail.com>"

    git -C "$REPO_DIR" push origin main
    log "Pushed to GitHub — Hostinger deploy triggered."
else
    log "Nothing committed (dry-run=$DRY_RUN)."
fi

log "=== Done ==="
