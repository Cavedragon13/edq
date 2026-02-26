#!/bin/bash
# publish_gallery.sh — Upload a Dragonart gallery ZIP to seed13.com
#
# Usage:
#   bash scripts/publish_gallery.sh "King of the Concrete Jungle_gallery.zip"
#   bash scripts/publish_gallery.sh "Golden Drake_gallery.zip" --delete
#   bash scripts/publish_gallery.sh --list
#
# Looks for ZIPs in ~/Downloads if no path given

set -e
cd /srv/containers/edq

ZIP="$1"

# If just a filename (no path), look in ~/Downloads first
if [ -n "$ZIP" ] && [ "$ZIP" != "--list" ] && [ ! -f "$ZIP" ]; then
    if [ -f "/home/edq/Downloads/$ZIP" ]; then
        ZIP="/home/edq/Downloads/$ZIP"
    fi
fi

exec python3 scripts/publish_gallery.py "$ZIP" "${2:-}"
