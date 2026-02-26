#!/bin/bash
# Backup all Claude Code critical files to ancalagon NAS
# Includes: CLAUDE.md files, memory files, conversation history, plan files
# Runs as part of nightly cron job at 0210 (2:10 AM)
#
# SETUP: Mount ancalagon SMB share in /etc/fstab for automatic mounting:
# //ancalagon.lan/backups  /mnt/ancalagon  cifs  username=edq,uid=edq,gid=edq,nounix,iocharset=utf8  0  0
# OR for Tailscale:
# //100.100.225.124/backups  /mnt/ancalagon  cifs  username=edq,uid=edq,gid=edq,nounix,iocharset=utf8  0  0

set -e

BACKUP_DATE=$(date +%Y-%m-%d)
BACKUP_TIME=$(date +%Y-%m-%d_%H-%M-%S)
BACKUP_ROOT="/mnt/ancalagon/backups/claude"
BACKUP_DIR="$BACKUP_ROOT/$BACKUP_DATE"

# Ensure ancalagon SMB share is mounted
if [ ! -d "/mnt/ancalagon" ]; then
  mkdir -p /mnt/ancalagon

  # Try to mount ancalagon SMB share via Tailscale or LAN
  # ancalagon: Synology NAS, SMB (445/139) open, reachable via Tailscale subnet route
  echo "[$(date)] Mounting ancalagon SMB share..."

  # Try Tailscale route first (100.100.225.124 from udragon)
  if mount -t cifs //100.100.225.124/backups -o username=edq,uid=edq,gid=edq /mnt/ancalagon 2>/dev/null; then
    echo "[$(date)] Mounted via Tailscale"
  # Try LAN mDNS name (ancalagon.lan)
  elif mount -t cifs //ancalagon.lan/backups -o username=edq,uid=edq,gid=edq /mnt/ancalagon 2>/dev/null; then
    echo "[$(date)] Mounted via LAN (ancalagon.lan)"
  else
    echo "[$(date)] Warning: Could not mount ancalagon. Using local fallback..."
    BACKUP_ROOT="/tmp/claude_backups"
  fi
fi

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting Claude Code backup to ancalagon..."

# Backup 1: Project CLAUDE.md and docs/
echo "  • Backing up /srv/containers/edq/CLAUDE.md and docs/..."
mkdir -p "$BACKUP_DIR/srv-containers-edq"
cp /srv/containers/edq/CLAUDE.md "$BACKUP_DIR/srv-containers-edq/"
cp -r /srv/containers/edq/docs "$BACKUP_DIR/srv-containers-edq/" 2>/dev/null || true

# Backup 2: Memory files from ~/.claude/projects/-srv-containers-edq/memory/
echo "  • Backing up memory files..."
mkdir -p "$BACKUP_DIR/memory"
cp -r /home/edq/.claude/projects/-srv-containers-edq/memory/* "$BACKUP_DIR/memory/" 2>/dev/null || true

# Backup 3: Claude Code conversations (all .jsonl files)
echo "  • Backing up conversation history..."
mkdir -p "$BACKUP_DIR/conversations"
find /home/edq/.claude/projects -maxdepth 2 -name "*.jsonl" -exec cp {} "$BACKUP_DIR/conversations/" \; 2>/dev/null || true

# Backup 4: Plan files
echo "  • Backing up plan files..."
mkdir -p "$BACKUP_DIR/plans"
cp -r /home/edq/.claude/plans/* "$BACKUP_DIR/plans/" 2>/dev/null || true

# Backup 5: Knowledge base Claude-related files
echo "  • Backing up knowledge base Claude files..."
mkdir -p "$BACKUP_DIR/knowledge-base"
cp /home/edq/knowledge-base/AI\ Projects/CLAUDE.md "$BACKUP_DIR/knowledge-base/CLAUDE-AI-Projects.md" 2>/dev/null || true
cp /home/edq/knowledge-base/.claude/CLAUDE.md "$BACKUP_DIR/knowledge-base/CLAUDE-dot-claude.md" 2>/dev/null || true
cp -r "/home/edq/knowledge-base/AI Projects/Memory" "$BACKUP_DIR/knowledge-base/" 2>/dev/null || true

# Create manifest with backup metadata
cat > "$BACKUP_DIR/MANIFEST.txt" << 'EOF'
Claude Code Backup Manifest
===========================

Backup Contents:
- srv-containers-edq/CLAUDE.md (main project documentation)
- srv-containers-edq/docs/ (topic-specific documentation)
- memory/ (MEMORY.md, common_issues.md, gpu_optimization.md, web_ui_patterns.md, etc.)
- conversations/ (all .jsonl conversation files with UUIDs)
- plans/ (plan files from EnterPlanMode tool)
- knowledge-base/ (CLAUDE.md files from knowledge base, Memory folder)

CRITICAL LESSON (2026-02-20):
When deleting symlinks, ALWAYS verify that actual files still exist in the target directory.
Deleting self-referential symlinks can accidentally delete the files they point to.
Always confirm: ls -la <target-dir>/ before and after symlink deletion.

Recovery:
If files are lost again, restore from the most recent dated backup:
  cp -r /mnt/ancalagon/backups/claude/YYYY-MM-DD/* ~/restore-location/
EOF

# Summary
BACKUP_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
FILE_COUNT=$(find "$BACKUP_DIR" -type f | wc -l)

echo "[$(date)] Backup complete!"
echo "  Location: $BACKUP_DIR"
echo "  Size: $BACKUP_SIZE"
echo "  Files: $FILE_COUNT"

# Keep only last 7 days of daily backups
echo "  • Cleaning old backups (keeping last 7 days)..."
find "$BACKUP_ROOT" -maxdepth 1 -type d -name "20[0-9][0-9]-*" -mtime +7 -exec rm -rf {} \; 2>/dev/null || true

echo "[$(date)] Claude Code backup finished."
