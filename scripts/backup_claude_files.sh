#!/bin/bash
# Backup all Claude Code critical files to ancalagon NAS
# Includes: CLAUDE.md files, memory files, conversation history, plan files
# Runs as part of nightly cron job at 0210 (2:10 AM)
# Also scrubs known credentials from all agent transcripts (scrub_transcripts.py) and locks file permissions.
#
# If ancalagon can't be mounted, the backup still runs, but into a local folder that
# survives reboots (not /tmp), the run is logged as FAILED, and an attention row is
# written so the next session / overnight report surfaces it. (Ed, 2026-10-25: the old
# /tmp fallback silently reported "Backup complete!" for days while the NAS was down.)

set -e

source /srv/containers/edq/.env

BACKUP_DATE=$(date +%Y-%m-%d)
NAS_ROOT="/mnt/ancalagon_backup/Cavedragon/Drive/sys/claude"
LOCAL_ROOT="/srv/containers/edq/backups/claude-local"
ATTENTION="/srv/containers/edq/logs/weekly_update_attention.md"
BACKUP_ROOT="$NAS_ROOT"
NAS_OK=1

# --- Step 1: Scrub known credentials from all agent transcripts ---
# Claude, Codex, Gemini/Antigravity, OpenCode, Grok, Kimi, Hermes.
# See scrub_transcripts.py for paths; secrets list: ~/.claude/scrub-credentials.txt
echo "[$(date)] Scrubbing credentials from agent transcripts..."
python3 /srv/containers/edq/scripts/scrub_transcripts.py || echo "  WARNING: scrub failed; continuing with backup"
echo "[$(date)] Scrubbing credentials from Mac transcripts (cdragon, odragon, adragon)..."
/srv/containers/edq/scripts/scrub_remote_macs.sh || echo "  WARNING: Mac scrub failed; continuing with backup"

# --- Step 2: Lock down conversation file permissions ---
echo "[$(date)] Setting conversation file permissions..."
find /home/edq/.claude/projects/ -type f -exec chmod 600 {} \;
find /home/edq/.claude/projects/ -type d -exec chmod 700 {} \;

# --- Step 3: Mount ancalagon homes share ---
mkdir -p /mnt/ancalagon_backup
if ! mountpoint -q /mnt/ancalagon_backup; then
  echo "[$(date)] Mounting ancalagon homes share..."
  if sudo mount -t cifs //192.168.7.160/homes -o username=admin,password="${ANCALAGON_SSH_PASS}",uid=edq,gid=edq /mnt/ancalagon_backup 2>/dev/null; then
    echo "[$(date)] Mounted via IP (192.168.7.160)"
  else
    NAS_OK=0
    BACKUP_ROOT="$LOCAL_ROOT"
    echo "[$(date)] ❌ ERROR: could not mount ancalagon (//192.168.7.160/homes)."
    echo "[$(date)]    Backing up to $LOCAL_ROOT instead (survives reboots, NOT off-machine)."
  fi
fi
BACKUP_DIR="$BACKUP_ROOT/$BACKUP_DATE"

# Create backup directory
mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting Claude Code backup to $([ "$NAS_OK" = 1 ] && echo ancalagon || echo 'LOCAL FALLBACK')..."

# Backup 1: Project CLAUDE.md and docs/
echo "  • Backing up /srv/containers/edq/CLAUDE.md and docs/..."
mkdir -p "$BACKUP_DIR/srv-containers-edq"
cp /srv/containers/edq/CLAUDE.md "$BACKUP_DIR/srv-containers-edq/"
cp -r /srv/containers/edq/docs "$BACKUP_DIR/srv-containers-edq/" 2>/dev/null || true

# Backup 2: Memory files
echo "  • Backing up memory files..."
mkdir -p "$BACKUP_DIR/memory"
cp -r /home/edq/.claude/projects/-srv-containers-edq/memory/* "$BACKUP_DIR/memory/" 2>/dev/null || true

# Backup 3: Conversation history (already scrubbed above)
echo "  • Backing up conversation history..."
mkdir -p "$BACKUP_DIR/conversations"
find /home/edq/.claude/projects -maxdepth 2 -name "*.jsonl" -exec cp {} "$BACKUP_DIR/conversations/" \; 2>/dev/null || true

# Backup 4: Plan files
echo "  • Backing up plan files..."
mkdir -p "$BACKUP_DIR/plans"
cp -r /home/edq/.claude/plans/* "$BACKUP_DIR/plans/" 2>/dev/null || true

# Backup 5: settings.json
echo "  • Backing up settings.json..."
cp /home/edq/.claude/settings.json "$BACKUP_DIR/" 2>/dev/null || true

# Summary
BACKUP_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
FILE_COUNT=$(find "$BACKUP_DIR" -type f | wc -l)

# Keep only last 14 days of daily backups
echo "  • Cleaning old backups (keeping last 14 days)..."
find "$BACKUP_ROOT" -maxdepth 1 -type d -name "20[0-9][0-9]-*" -mtime +14 -exec rm -rf {} \; 2>/dev/null || true

# Unmount
sudo umount /mnt/ancalagon_backup 2>/dev/null || true

if [ "$NAS_OK" = 1 ]; then
  # Clear any earlier fallback alert now that the NAS is reachable again.
  [ -f "$ATTENTION" ] && sed -i '/| Claude backup |/d' "$ATTENTION"
  echo "[$(date)] Backup complete!"
  echo "  Location: $BACKUP_DIR"
  echo "  Size: $BACKUP_SIZE"
  echo "  Files: $FILE_COUNT"
  echo "[$(date)] Claude Code backup finished."
  exit 0
fi

# Fallback path: say so loudly and leave an attention row (one per day, no duplicates).
row="- | Claude backup | ancalagon unreachable — nightly backup went to $LOCAL_ROOT (on udragon, not off-machine) since $BACKUP_DATE | check the NAS is on and at 192.168.7.160 |"
if [ ! -f "$ATTENTION" ]; then
  printf '# Needs attention\n\nAuto-generated. Rows clear themselves once resolved.\n\n' > "$ATTENTION"
fi
grep -q '| Claude backup |' "$ATTENTION" || echo "$row" >> "$ATTENTION"
echo "[$(date)] ❌ Backup FAILED to reach ancalagon — local copy only."
echo "  Location: $BACKUP_DIR"
echo "  Size: $BACKUP_SIZE"
echo "  Files: $FILE_COUNT"
exit 1
