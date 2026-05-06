#!/usr/bin/env bash
# verify_gallery.sh — spot-check that a deployed gallery has real images
# Usage: ./verify_gallery.sh https://seed13.com/galleries/dwarves/ full/dwarf_viking_dwarf_001.png
set -euo pipefail

GALLERY_URL="${1:?Usage: verify_gallery.sh GALLERY_BASE_URL IMAGE_PATH}"
IMAGE_PATH="${2:?Provide a relative image path to test}"

IMAGE_URL="${GALLERY_URL%/}/${IMAGE_PATH}"
echo "Checking: $IMAGE_URL"

HTTP_CODE=$(curl -s -o /tmp/verify_img -w "%{http_code}" "$IMAGE_URL")
FILE_SIZE=$(wc -c < /tmp/verify_img)
CONTENT_TYPE=$(file --mime-type -b /tmp/verify_img)

echo "HTTP: $HTTP_CODE | Size: ${FILE_SIZE} bytes | Type: $CONTENT_TYPE"

if [[ "$HTTP_CODE" != "200" ]]; then
    echo "FAIL: HTTP $HTTP_CODE"
    exit 1
elif [[ "$FILE_SIZE" -lt 10240 ]]; then
    echo "FAIL: File too small (${FILE_SIZE} bytes) — likely an LFS stub or error page"
    exit 1
elif [[ "$CONTENT_TYPE" != image/* ]]; then
    echo "FAIL: Wrong content type ($CONTENT_TYPE)"
    exit 1
else
    echo "PASS: Real image confirmed"
fi
