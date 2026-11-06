#!/bin/bash
# backup_vaultwarden.sh — nightly encrypted backup of udragon's Vaultwarden (snap) to ancalagon.
# Cron: 02:20 daily. Added 2026-11-06: the live vault had NO backup of any kind.
#
# What: a consistent SQLite snapshot (online backup API, safe while Vaultwarden runs), the
# server's rsa_key.pem, any attachments/sends, and the snap's .env, tarred and encrypted with
# gpg (AES256) using VAULTWARDEN_BACKUP_PASSPHRASE from /srv/containers/edq/.env.
# Where: /mnt/ancalagon/Cavedragon/Drive/sys/vaultwarden/vaultwarden_<ts>.tar.gz.gpg (keeps 30).
# Each run test-decrypts its own archive and runs PRAGMA integrity_check on the copy, and only
# then prints the success line that scripts/automation_check.py looks for.
#
# Restore: see the "Vaultwarden backup" section in ~/knowledge-base/claude-sync/network.md.
set -euo pipefail

SRC=/var/snap/vaultwarden/current
DEST=/mnt/ancalagon/Cavedragon/Drive/sys/vaultwarden
KEEP=30
TS=$(date +%Y%m%d_%H%M%S)
log() { echo "[$(date '+%F %T')] $*"; }

PASS=$(grep -E '^VAULTWARDEN_BACKUP_PASSPHRASE=' /srv/containers/edq/.env | cut -d= -f2-)
[ -n "$PASS" ] || { log "ERROR: VAULTWARDEN_BACKUP_PASSPHRASE missing from .env"; exit 1; }

WORK=$(mktemp -d)
chmod 700 "$WORK"
trap 'sudo -n rm -rf "$WORK"' EXIT
mkdir -p "$WORK/vaultwarden/data"

log "Snapshotting Vaultwarden database"
sudo -n python3 - "$SRC/data/db.sqlite3" "$WORK/vaultwarden/data/db.sqlite3" <<'PYEOF'
import sqlite3, sys
src = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
dst = sqlite3.connect(sys.argv[2])
src.backup(dst)
dst.close(); src.close()
PYEOF
sudo -n cp "$SRC/data/rsa_key.pem" "$WORK/vaultwarden/data/"
sudo -n cp "$SRC/.env" "$WORK/vaultwarden/snap.env"
for d in attachments sends; do
    if sudo -n test -d "$SRC/data/$d"; then sudo -n cp -r "$SRC/data/$d" "$WORK/vaultwarden/data/"; fi
done
sudo -n chown -R "$(id -u):$(id -g)" "$WORK/vaultwarden"

mkdir -p "$DEST"
OUT="$DEST/vaultwarden_$TS.tar.gz.gpg"
tar -C "$WORK" -czf - vaultwarden \
    | gpg --batch --yes --quiet --pinentry-mode loopback --passphrase-fd 3 \
          --symmetric --cipher-algo AES256 -o "$OUT" 3<<<"$PASS"

log "Verifying $OUT"
mkdir "$WORK/verify"
gpg --batch --quiet --pinentry-mode loopback --passphrase-fd 3 -d "$OUT" 3<<<"$PASS" | tar -C "$WORK/verify" -xzf -
RESULT=$(python3 -I - "$WORK/verify/vaultwarden/data/db.sqlite3" <<'PYEOF'
import sqlite3, sys
c = sqlite3.connect(sys.argv[1])
ok = c.execute("pragma integrity_check").fetchone()[0]
n = c.execute("select count(*) from ciphers").fetchone()[0]
u = c.execute("select count(*) from users").fetchone()[0]
print(f"{ok} {n} {u}")
PYEOF
)
read -r OK NCIPHERS NUSERS <<<"$RESULT"
if [ "$OK" != "ok" ] || [ "$NUSERS" -lt 1 ]; then
    log "ERROR: restored copy failed verification (integrity=$OK users=$NUSERS)"; exit 1
fi

# Retention: newest $KEEP archives
ls -1t "$DEST"/vaultwarden_*.tar.gz.gpg 2>/dev/null | tail -n +$((KEEP + 1)) | while read -r old; do rm -f -- "$old"; done

log "vaultwarden backup finished: $(basename "$OUT") ($(du -h "$OUT" | cut -f1)), $NCIPHERS items, $NUSERS user(s), integrity ok"
