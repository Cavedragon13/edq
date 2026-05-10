#!/bin/bash
set -e

echo "🖼️  Starting Downloads Gallery on port 8060..."
exec /srv/containers/edq/venv_dl_gallery/bin/python /srv/containers/edq/scripts/dl_gallery.py
