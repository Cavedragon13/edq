#!/bin/bash
set -e

# backup_bookmarks.sh — Phase 1 of bookmark centralization
# Read-only SSH copies of all bookmark files from all machines.
# NEVER writes to any browser profile. Safe to re-run.

BACKUP_BASE="/srv/containers/edq/media/bookmark_backups"
DATE=$(date +%Y-%m-%d)
BACKUP_DIR="$BACKUP_BASE/$DATE"

echo "=================================================="
echo "  Bookmark Backup — $(date)"
echo "=================================================="
echo ""

# Refuse to overwrite an existing backup for today
if [ -d "$BACKUP_DIR" ]; then
    echo "[!] Backup dir already exists: $BACKUP_DIR"
    echo "    To force a new backup, rename or remove it first."
    echo "    Existing backup is intact — exiting safely."
    exit 1
fi

mkdir -p "$BACKUP_DIR"
echo "[+] Backup dir: $BACKUP_DIR"
echo ""

fail=0
copy_file() {
    local label="$1"
    local src="$2"
    local dest="$3"
    echo -n "    $label ... "
    if scp -q "$src" "$dest" 2>/dev/null; then
        local size
        size=$(du -h "$dest" | cut -f1)
        echo "OK ($size)"
    else
        echo "FAILED (skipped)"
        fail=$((fail + 1))
    fi
}

# ── udragon (local) ───────────────────────────────────────────────────────────
echo "[udragon] Chrome"
copy_file "Bookmarks" \
    "/home/edq/.config/google-chrome/Default/Bookmarks" \
    "$BACKUP_DIR/udragon_chrome_Bookmarks"
copy_file "Bookmarks.bak" \
    "/home/edq/.config/google-chrome/Default/Bookmarks.bak" \
    "$BACKUP_DIR/udragon_chrome_Bookmarks.bak"
echo ""

# ── odragon (Mac Mini M4 Pro) ─────────────────────────────────────────────────
echo "[odragon] Chrome + Safari"
copy_file "Chrome/Bookmarks" \
    "odragon:Library/Application Support/Google/Chrome/Default/Bookmarks" \
    "$BACKUP_DIR/odragon_chrome_Bookmarks"
copy_file "Safari/Bookmarks.plist" \
    "odragon:Library/Safari/Bookmarks.plist" \
    "$BACKUP_DIR/safari_Bookmarks.plist"
echo ""

# ── cdragon (MacBook Pro M5) ──────────────────────────────────────────────────
echo "[cdragon] Chrome + Edge (Safari skipped — same iCloud set as odragon)"
copy_file "Chrome/Bookmarks" \
    "cdragon:Library/Application Support/Google/Chrome/Default/Bookmarks" \
    "$BACKUP_DIR/cdragon_chrome_Bookmarks"
copy_file "Edge/Bookmarks" \
    "cdragon:Library/Application Support/Microsoft Edge/Default/Bookmarks" \
    "$BACKUP_DIR/cdragon_edge_Bookmarks"
echo ""

# ── adragon (MacBook Air) ─────────────────────────────────────────────────────
echo "[adragon] Chrome (Safari skipped — same iCloud set as odragon)"
copy_file "Chrome/Bookmarks" \
    "adragon:Library/Application Support/Google/Chrome/Default/Bookmarks" \
    "$BACKUP_DIR/adragon_chrome_Bookmarks"
echo ""

# ── Manifest ──────────────────────────────────────────────────────────────────
echo "[+] Writing MANIFEST.txt..."
{
    echo "Bookmark Backup Manifest"
    echo "Generated: $(date)"
    echo "Directory: $BACKUP_DIR"
    echo ""
    echo "File                         Size      MD5"
    echo "-------------------------------------------------------------------"
    for f in "$BACKUP_DIR"/*; do
        fname=$(basename "$f")
        if [ "$fname" = "MANIFEST.txt" ]; then continue; fi
        fsize=$(du -h "$f" | cut -f1)
        fmd5=$(md5sum "$f" | cut -d' ' -f1)
        printf "%-30s %-9s %s\n" "$fname" "$fsize" "$fmd5"
    done
} > "$BACKUP_DIR/MANIFEST.txt"

echo ""
cat "$BACKUP_DIR/MANIFEST.txt"
echo ""

if [ $fail -gt 0 ]; then
    echo "[!] $fail file(s) failed to copy — check SSH access and paths."
    echo "    All successful copies are intact in: $BACKUP_DIR"
    exit 1
else
    echo "[✓] All files backed up successfully."
    echo "    Backup dir: $BACKUP_DIR"
fi
