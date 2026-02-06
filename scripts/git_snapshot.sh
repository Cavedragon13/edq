#!/bin/bash
# Dragonsuite Git Snapshot - Auto-commit changed files
# Run this before reboots or major changes

set -e

cd /srv/containers/edq

# Check if there are any changes
if [[ -z $(git status --porcelain) ]]; then
    echo "✓ No changes to commit"
    exit 0
fi

# Show what changed
echo "📝 Changes detected:"
git status --short

# Create snapshot commit
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
git add -A
git commit -m "Auto-snapshot: $TIMESTAMP

Modified files saved before system change/reboot.
This is an automatic backup commit." || echo "⚠️  Commit failed (may be no changes)"

echo "✓ Snapshot saved! Latest commit:"
git log --oneline -1
