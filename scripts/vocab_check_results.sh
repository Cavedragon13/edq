#!/bin/bash
# Quick status check for translation pipeline results

BASE_DIR="/srv/containers/edq/translations"

echo "=== Translation Pipeline Status ==="
echo ""
echo "✓ Approved:      $(ls -1 $BASE_DIR/approved/*.json 2>/dev/null | wc -l) files"
echo "⚠ Needs Review:  $(ls -1 $BASE_DIR/needs_review/*.json 2>/dev/null | wc -l) files"
echo "✗ Rejected:      $(ls -1 $BASE_DIR/rejected/*.json 2>/dev/null | wc -l) files"
echo ""
echo "--- Recent QC Reports ---"
ls -lt $BASE_DIR/qc/*.json | head -5 | awk '{print $9}' | xargs -I {} basename {}
echo ""

if [ "$1" == "--approved" ]; then
    echo "=== Approved Translations ==="
    for file in $BASE_DIR/approved/*.json; do
        if [ -f "$file" ]; then
            echo ""
            echo "$(basename $file):"
            jq -r '"\(.word_id) [\(.target_lang)]: \(.translation) (confidence: \(.confidence)%)"' "$file"
        fi
    done
fi

if [ "$1" == "--review" ]; then
    echo "=== Translations Needing Review ==="
    for file in $BASE_DIR/needs_review/*.json; do
        if [ -f "$file" ]; then
            echo ""
            echo "$(basename $file):"
            jq -r '"\(.word_id) [\(.target_lang)]: \(.translation) (confidence: \(.confidence)%)"' "$file"
        fi
    done
fi
