#!/bin/bash
# Backup all Claude Code critical files to ancalagon NAS
# Includes: CLAUDE.md files, memory files, conversation history, plan files
# Runs as part of nightly cron job at 0210 (2:10 AM)
# Also scrubs known credentials from conversation history and locks file permissions.

set -e

source /srv/containers/edq/.env

BACKUP_DATE=$(date +%Y-%m-%d)
BACKUP_ROOT="/mnt/ancalagon_backup/Cavedragon/Drive/sys/claude"
BACKUP_DIR="$BACKUP_ROOT/$BACKUP_DATE"

# --- Step 1: Scrub known credentials from conversation history ---
echo "[$(date)] Scrubbing credentials from conversation history..."
python3 << 'PYEOF'
import pathlib

REPLACEMENTS = {
    "galactic-diagnosis-ambulance": "<vault-password-redacted>",
    "1324b0X0": "<adragon-ssh-password-redacted>",
    "3nqJPqhbjo24": "<ancalagon-ssh-password-redacted>",
    "8ae645c9-5f8b-473a-9150-d4757b70fc79": "<smithery-key-redacted>",
    "REDACTED_SUPABASE_KEY": "<supabase-secret-redacted>",
}

root = pathlib.Path.home() / ".claude/projects"
changed = 0
replacements = 0
for f in root.rglob("*.jsonl"):
    try:
        text = f.read_text(errors="replace")
        new_text = text
        for cred, placeholder in REPLACEMENTS.items():
            count = new_text.count(cred)
            if count:
                replacements += count
                new_text = new_text.replace(cred, placeholder)
        if new_text != text:
            f.write_text(new_text)
            changed += 1
    except Exception as e:
        print(f"  Warning: could not process {f}: {e}")

print(f"  Scrubbed {changed} files, {replacements} replacements")
PYEOF

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
    echo "[$(date)] Warning: Could not mount ancalagon. Using local fallback..."
    BACKUP_ROOT="/tmp/claude_backups/claude"
    BACKUP_DIR="$BACKUP_ROOT/$BACKUP_DATE"
  fi
fi

# Create backup directory
mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting Claude Code backup to ancalagon..."

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

echo "[$(date)] Backup complete!"
echo "  Location: $BACKUP_DIR"
echo "  Size: $BACKUP_SIZE"
echo "  Files: $FILE_COUNT"

# Keep only last 14 days of daily backups
echo "  • Cleaning old backups (keeping last 14 days)..."
find "$BACKUP_ROOT" -maxdepth 1 -type d -name "20[0-9][0-9]-*" -mtime +14 -exec rm -rf {} \; 2>/dev/null || true

# Unmount
sudo umount /mnt/ancalagon_backup 2>/dev/null || true

echo "[$(date)] Claude Code backup finished."
