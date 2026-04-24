#!/bin/bash
set -e

echo "🖼️  Starting Downloads Gallery on port 8060..."
exec python3 /srv/containers/edq/scripts/dl_gallery.py
