#!/usr/bin/env bash
# Image an old drive (attached via USB/IDE/SATA adapter) to a raw file with
# ddrescue, capture SMART if the bridge passes it through, and log it.
#
# Usage: image_drive.sh /dev/sdX "label"
# Example: image_drive.sh /dev/sda "caviar2200-unicorn"
set -euo pipefail

BASE="/srv/containers/edq/drive-archaeology"
IMAGES="$BASE/images"
LOG="$BASE/log.csv"

ASSUME_YES=0
if [ "${1:-}" = "--yes" ]; then
    ASSUME_YES=1
    shift
fi

if [ $# -lt 1 ]; then
    echo "Usage: $0 [--yes] /dev/sdX \"label\"" >&2
    exit 1
fi

DEV="$1"
LABEL="${2:-unlabeled}"

# When already root (e.g. invoked via the narrowly-scoped sudoers rule for
# this exact script), don't re-sudo internally — root running sudo against
# itself is unnecessary and fragile under a non-interactive caller.
SUDO="sudo"
[ "$(id -u)" -eq 0 ] && SUDO=""

# Refuse to touch the machine's own system disks, no matter what.
case "$DEV" in
    /dev/nvme0n1*|/dev/nvme1n1*)
        echo "Refusing: $DEV is a system disk on this machine, not a target drive." >&2
        exit 1
        ;;
esac

if [ ! -b "$DEV" ]; then
    echo "$DEV is not a block device (check 'lsblk' for the right name)." >&2
    exit 1
fi

echo "=== Device info ==="
lsblk -o NAME,SIZE,MODEL,SERIAL,TRAN,VENDOR "$DEV"
echo

if [ "$ASSUME_YES" -eq 1 ]; then
    echo "--yes given, skipping interactive confirmation."
else
    read -r -p "Image this device to $IMAGES ? Type 'yes' to continue: " CONFIRM
    if [ "$CONFIRM" != "yes" ]; then
        echo "Aborted."
        exit 1
    fi
fi

DATE=$(date +%Y%m%d_%H%M%S)
SLUG=$(echo "$LABEL" | tr -c 'A-Za-z0-9_-' '-')
OUTDIR="$IMAGES/${DATE}_${SLUG}"
mkdir -p "$OUTDIR"

echo "=== SMART info (many cheap USB bridges don't pass this through — that's OK) ==="
{
    $SUDO smartctl -a "$DEV" || echo "SMART unavailable via this adapter/drive."
} | tee "$OUTDIR/smart.txt"

echo
echo "=== Pass 1: fast rescue pass (skip scraping, grab all easy data first) ==="
$SUDO ddrescue -n "$DEV" "$OUTDIR/image.img" "$OUTDIR/image.mapfile"

echo
echo "=== Pass 2: retry bad areas (up to 3 retries) ==="
$SUDO ddrescue -r3 "$DEV" "$OUTDIR/image.img" "$OUTDIR/image.mapfile"

echo
echo "=== Done ==="
echo "Image:    $OUTDIR/image.img"
echo "Mapfile:  $OUTDIR/image.mapfile"
echo "SMART:    $OUTDIR/smart.txt"

if [ ! -f "$LOG" ]; then
    echo "date,label,device,image_path,status,notes" > "$LOG"
fi
echo "${DATE},${LABEL},${DEV},${OUTDIR}/image.img,imaged," >> "$LOG"
echo
echo "Logged to $LOG"
echo
echo "Next, inspect the IMAGE (never the physical drive directly):"
echo "  sudo losetup -fP --show \"$OUTDIR/image.img\"    # attach as loop device, prints e.g. /dev/loop0"
echo "  sudo testdisk \"$OUTDIR/image.img\"               # find partitions / recover if the table is gone"
echo "  sudo losetup -d /dev/loopN                       # detach when done"
