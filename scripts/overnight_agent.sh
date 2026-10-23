#!/bin/bash
# Overnight conformance agent — runs an unattended Claude Code session that works
# through ~/knowledge-base/Dragonsuite/Conformance.md using config/agent/overnight_runbook.md.
# Cron: 00:30 daily (after the 00:15 health/conformance check), inside Ed's midnight-04:00
# window. The supervisor stops idle GPU services for room and restarts them afterwards.
#
#   bash scripts/overnight_agent.sh            # normal run
#   DRY_RUN=1 bash scripts/overnight_agent.sh  # read-only: plan + report, change nothing
set -u
cd /srv/containers/edq
export PATH="/home/edq/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

DATE="$(date +%F)"
LOG_DIR="/srv/containers/edq/logs/overnight_agent"
LOG="$LOG_DIR/$DATE.log"
REPORT_DIR="/home/edq/knowledge-base/Dragonsuite/Overnight"
RUNBOOK="/srv/containers/edq/config/agent/overnight_runbook.md"
mkdir -p "$LOG_DIR" "$REPORT_DIR"

exec 9>"$LOG_DIR/.lock"
flock -n 9 || { echo "$(date '+%F %T') already running — skip" >> "$LOG"; exit 0; }

# The supervisor checks the GPU is idle, stops running GPU services (incl. Krea2) and
# restarts them afterwards. If the GPU is busy it stops nothing and GPU tests defer.
export OVERNIGHT_SERVICE_JOURNAL="$LOG_DIR/$DATE.services.json"
export OVERNIGHT_REPORT="$REPORT_DIR/$DATE.md"

PROMPT="$(cat "$RUNBOOK")"
if [[ "${DRY_RUN:-0}" == 1 ]]; then
    PROMPT="DRY RUN — do NOT change, launch or stop anything. Read the files listed under
'First, read', decide the 3 units you WOULD do tonight and how, then write the morning
report with a 'Dry run — planned' section instead of Done.

$PROMPT"
fi

echo "$(date '+%F %T') starting (dry_run=${DRY_RUN:-0})" >> "$LOG"
# --no-session-persistence: no transcript in ~/.claude/projects, so the ChatGPT app's
# Claude import never sees this run. Full output is in $LOG.
python3 scripts/overnight_supervisor.py claude -p "$PROMPT" --no-session-persistence \
    --permission-mode dontAsk \
    --allowedTools "Read" "Edit" "Write" "Glob" "Grep" "Bash" \
    --disallowedTools "Bash(sudo:*)" "Bash(rm -rf:*)" "Bash(git push:*)" "Bash(crontab:*)" \
                      "Bash(systemctl:*)" "Bash(dd:*)" "Bash(mkfs:*)" "Bash(shutdown:*)" "Bash(reboot:*)" \
    --add-dir /home/edq/knowledge-base /home/edq/ai_generated \
    --output-format text >> "$LOG" 2>&1
rc=$?
echo "$(date '+%F %T') finished rc=$rc" >> "$LOG"
if [[ "$rc" != 0 ]]; then
    printf '\nOvernight wrapper failed (rc=%s); inspect %s before retrying.\n' \
        "$rc" "$LOG" >> "$REPORT_DIR/$DATE.md"
fi
[[ -f "$REPORT_DIR/$DATE.md" ]] || printf '# Overnight %s\n\nThe agent exited (rc=%s) without writing a report — see %s\n' \
    "$DATE" "$rc" "$LOG" > "$REPORT_DIR/$DATE.md"
exit "$rc"
