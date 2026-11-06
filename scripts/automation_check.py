#!/usr/bin/env python3
"""
automation_check.py — did the automations actually WORK, not just run?

Added 2026-11-06 after a week of silent failures nobody could see: CLAUDE.md/AGENTS.md deleted
and the deletion auto-committed; NAS backups empty for 6 nights (set -e abort); nightly_commit.sh
dying mid-loop every night since ~Oct 20; nothing pushed to GitHub since Oct 31; /verify unable
to run. Each one logged an error to a file nobody reads.

This checks OUTCOMES (a fresh "done" line, a non-empty backup on the NAS, nothing left
unpushed, protected files present), never exit codes. `health_check.py --all` (00:15) calls it
and puts every problem at the TOP of Conformance.md as [automation] items, which the overnight
agent (00:30) must fix before anything else. It also writes logs/automation_attention.md, which
CLAUDE.md tells every session to read at start. Problems that persist get a day count, so a
stuck failure gets louder instead of quieter.

Run by hand:  python3 scripts/automation_check.py        (exit 1 if anything is wrong)
"""
from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import sys
import time
from pathlib import Path

BASE = Path("/srv/containers/edq")
LOGS = BASE / "logs"
ATTENTION = LOGS / "automation_attention.md"
STATE = LOGS / "automation_state.json"          # {problem key: first-seen date}
NAS_BACKUPS = Path("/mnt/ancalagon/Cavedragon/Drive/sys/claude")   # same share the backup mounts
DAY = 26          # hours: a daily cron job's log must be fresher than this
MIN_BACKUP_MB = 10

PROTECTED = ["CLAUDE.md", "AGENTS.md", ".mcp.json", "config/dragonsuite.json", "tasks/lessons.md"]

# (job, log file, max age in hours, regex that a SUCCESSFUL run leaves in its last lines, fix hint)
JOBS = [
    ("nightly_commit", "nightly_commit_cron.log", DAY, r"nightly_commit finished",
     "scripts/nightly_commit.sh died before its last step — read the end of the log for the failing command"),
    ("claude backup", "nightly_backup_cron.log", DAY, r"Claude Code backup finished",
     "scripts/backup_claude_files.sh aborted — read the end of the log"),
    ("sync_skills", "sync_skills_cron.log", DAY, r"Skills sync complete", "scripts/sync_skills.sh"),
    ("kb_compiler", "kb_compiler.log", DAY, r"KB Compiler done", "scripts/kb_compiler.py"),
    ("cleanup_test_artifacts", "cleanup_artifacts.log", DAY, r"cleanup_test_artifacts done",
     "scripts/cleanup_test_artifacts.sh"),
    ("check_claude_sync", "check_claude_sync.log", DAY, r"Done\. Drifted/broken: 0",
     "a machine's ~/.claude/CLAUDE.md symlink is broken or the check did not finish"),
    ("machine_inventory", "machine_inventory.log", DAY, r"wrote .*machines\.md", "scripts/gen_machine_inventory.py"),
    ("publish_queue", "publish_queue_cron.log", DAY, r"Nothing to do|Processed|processed|Done",
     "scripts/process_publish_queue.sh"),
    ("weekly_update", "weekly_update_cron.log", 8 * 24, r"Weekly update complete", "scripts/weekly_update.sh (Sundays 03:30)"),
    ("lint_knowledge_base", "lint_kb_cron.log", 32 * 24, r"Done —", "scripts/lint_knowledge_base.sh (monthly)"),
]


def _age_h(p: Path) -> float:
    return (time.time() - p.stat().st_mtime) / 3600


def _tail(p: Path, n: int = 40) -> list[str]:
    try:
        return p.read_text(errors="ignore").splitlines()[-n:]
    except OSError:
        return []


def check_jobs() -> list[tuple[str, str]]:
    out = []
    for job, log, max_h, ok_re, hint in JOBS:
        p = LOGS / log
        if not p.exists():
            out.append((f"job:{job}", f"**{job}**: log `{log}` does not exist — has it ever run? ({hint})"))
            continue
        age = _age_h(p)
        if age > max_h:
            out.append((f"stale:{job}", f"**{job}**: last log activity {age:.0f}h ago (expected < {max_h}h) — "
                                        f"cron entry missing or the job hangs? ({hint})"))
            continue
        tail = _tail(p)
        if not any(re.search(ok_re, ln) for ln in tail):
            last = next((ln.strip() for ln in reversed(tail) if ln.strip()), "(empty)")
            out.append((f"job:{job}", f"**{job}**: last run did not reach its success line. "
                                      f"Last line: `{last[:160]}` — {hint}"))
        elif any("Traceback (most recent call last)" in ln for ln in tail[-15:]):
            out.append((f"crash:{job}", f"**{job}**: Python traceback at the end of `{log}` — {hint}"))
    return out


def check_overnight_agent() -> list[tuple[str, str]]:
    out = []
    d = LOGS / "overnight_agent"
    logs = sorted(d.glob("20??-??-??.log"))
    if not logs:
        return [("overnight:none", "**overnight agent**: no run logs at all")]
    last = logs[-1]
    if _age_h(last) > DAY:
        out.append(("overnight:stale", f"**overnight agent**: last run log is {_age_h(last):.0f}h old"))
    text = last.read_text(errors="ignore")
    m = re.findall(r"finished rc=(\d+)", text)
    if not m:
        out.append(("overnight:unfinished", f"**overnight agent**: `{last.name}` has no 'finished' line — run killed?"))
    elif m[-1] != "0":
        out.append(("overnight:rc", f"**overnight agent**: last run exited rc={m[-1]} — see `{last}`"))
    report = Path.home() / "knowledge-base/Dragonsuite/Overnight" / f"{last.stem}.md"
    if report.exists() and "did not complete its morning report" in report.read_text(errors="ignore"):
        out.append(("overnight:noreport", f"**overnight agent**: {last.stem} run ended without its report "
                                          "(quit early — e.g. 'waiting on a background task')"))
    if not (d / f"{last.stem}.jsonl").exists() and last.stem >= "2026-11-07":
        out.append(("overnight:notranscript", f"**overnight agent**: no transcript `{last.stem}.jsonl` — "
                                              "unattended runs must leave one (overnight_agent.sh)"))
    return out


def check_protected() -> list[tuple[str, str]]:
    return [(f"protected:{f}", f"**{f}** is missing from /srv/containers/edq — sessions and the overnight "
                               "agent run without it. Restore: `git checkout HEAD -- " + f + "`")
            for f in PROTECTED if not (BASE / f).exists()]


def check_backup() -> list[tuple[str, str]]:
    try:
        dirs = sorted(p for p in NAS_BACKUPS.iterdir() if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.name))
    except OSError as e:
        return [("backup:nas", f"**claude backup**: cannot read {NAS_BACKUPS} ({e.strerror}) — NAS unreachable?")]
    good = []
    for p in reversed(dirs[-10:]):
        size = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
        if size >= MIN_BACKUP_MB * 1e6:
            good.append(p.name)
            break
    if not good:
        return [("backup:empty", f"**claude backup**: no backup ≥{MIN_BACKUP_MB}MB in the last 10 folders on the NAS")]
    age_days = (dt.date.today() - dt.date.fromisoformat(good[0])).days
    if age_days > 1:
        return [("backup:old", f"**claude backup**: newest complete NAS backup is {good[0]} ({age_days} days old); "
                               "newer folders are empty or missing")]
    return []


def _git(*args) -> str:
    return subprocess.run(["git", "-C", str(BASE), *args], capture_output=True, text=True).stdout.strip()


def check_git() -> list[tuple[str, str]]:
    out = []
    oldest = _git("log", "--format=%ct", "--reverse", "origin/master..master").splitlines()
    if oldest:
        age_d = (time.time() - int(oldest[0])) / 86400
        if age_d > 1.2:
            out.append(("git:unpushed", f"**edq repo**: {len(oldest)} commit(s) not on GitHub, oldest "
                                        f"{age_d:.0f} days — nightly push not happening"))
    n_untracked = len(_git("ls-files", "--others", "--exclude-standard").splitlines())
    if n_untracked > 5000:
        out.append(("git:untracked", f"**edq repo**: {n_untracked:,} untracked files — gstack /verify times out "
                                     "above a few thousand; add the bulky folder to .gitignore"))
    for name in ("nightly_commit_attention.md", "weekly_update_attention.md"):
        p = LOGS / name
        if p.exists() and _age_h(p) > 3 * 24:
            out.append((f"stale-attention:{name}", f"**{name}** has not been rewritten for {_age_h(p) / 24:.0f} days "
                                                   "— the job that owns it is not reaching its end"))
    return out


def collect() -> list[tuple[str, str]]:
    return check_protected() + check_jobs() + check_overnight_agent() + check_backup() + check_git()


def with_age(problems: list[tuple[str, str]]) -> list[str]:
    """Attach 'failing for N days' using a first-seen record; forget keys that cleared."""
    today = dt.date.today().isoformat()
    try:
        seen = json.loads(STATE.read_text())
    except (OSError, ValueError):
        seen = {}
    seen = {k: v for k, v in seen.items() if k in {k for k, _ in problems}}
    lines = []
    for key, text in problems:
        first = seen.setdefault(key, today)
        days = (dt.date.today() - dt.date.fromisoformat(first)).days
        lines.append(text + (f" — **failing {days + 1} days (since {first})**" if days else " — new today"))
    STATE.write_text(json.dumps(seen, indent=1, sort_keys=True))
    return lines


def write_attention(lines: list[str]) -> None:
    if not lines:
        ATTENTION.unlink(missing_ok=True)
        return
    ATTENTION.write_text(
        f"# Automations failing — {dt.datetime.now():%Y-%m-%d %H:%M}\n\n"
        "Written by `scripts/automation_check.py` (via health_check, 00:15). The overnight agent fixes these\n"
        "first; anything it is not allowed to fix lands in its morning report under Needs Ed.\n\n"
        + "\n".join(f"- {ln}" for ln in lines) + "\n")


def main() -> int:
    lines = with_age(collect())
    write_attention(lines)
    print("\n".join(f"- {ln}" for ln in lines) if lines else "All automations healthy.")
    return 1 if lines else 0


if __name__ == "__main__":
    sys.exit(main())
