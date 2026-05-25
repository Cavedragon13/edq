#!/bin/bash
set -e

ARTIFACTS_DIR="$HOME/ai_generated/test-artifacts"
SCREENSHOTS_DIR="$HOME/Pictures/Screenshots"

echo "[$(date '+%Y-%m-%d %H:%M')] cleanup_test_artifacts start"

for dir in "$ARTIFACTS_DIR" "$SCREENSHOTS_DIR"; do
    if [ -d "$dir" ]; then
        count=$(find "$dir" -type f -mtime +30 2>/dev/null | wc -l)
        if [ "$count" -gt 0 ]; then
            find "$dir" -type f -mtime +30 -delete
            echo "  deleted $count files older than 30d from $dir"
        fi
    fi
done

echo "[$(date '+%Y-%m-%d %H:%M')] cleanup_test_artifacts done"
