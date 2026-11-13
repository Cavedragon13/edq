#!/usr/bin/env python3
"""scrub_transcripts.py — replace known secrets in AI agent transcripts.

Secrets come from two places, merged at run time:

  1. ~/.claude/scrub-credentials.txt (one "secret:placeholder" per line,
     chmod 600) — hand-kept entries. These win if both sources list a secret.
  2. Every value in the .env files below whose key name looks like a secret
     (PASS, PASSWORD, SECRET, TOKEN, KEY, CREDENTIAL, URI, DSN). The placeholder
     is "<KEY_NAME-redacted>". Add a password to an .env and it is scrubbed
     from the next nightly run on, with no list to maintain.
       /srv/containers/edq/.env
       /srv/containers/edq/docker/*/.env

Env values are skipped when they are shorter than 8 characters, contain
whitespace, or look like a URL/host/user/port setting (a bare word such as a
6-character password would also rewrite ordinary prose, so keep those in the
hand-kept list only if you accept that).

Then every literal occurrence of each secret is replaced in the transcript
files of every agent found on this machine.

Covered (paths checked 2026-09-23 on udragon and cdragon):
  Claude Code   ~/.claude/projects/**/*.jsonl
  Codex         ~/.codex/sessions/**/*.jsonl|json, ~/.codex/*.jsonl
  Gemini CLI    ~/.gemini/tmp/**/*.json
  Antigravity   ~/.gemini/antigravity/brain/**/*.json|md
  OpenCode      ~/.local/share/opencode/storage/**/*.json
  Grok CLI      ~/.grok/**/*.json|jsonl
  Kimi          ~/.kimi-work/**/*.json|jsonl (excluding bin/)
  Hermes        ~/.hermes/**/*.json|jsonl

Not rewritten: SQLite databases (e.g. OpenCode's opencode.db). Changing text
inside a database file byte-for-byte can corrupt it, so they are listed as
"skipped" in the summary instead.

Files modified in the last 10 minutes are skipped: an agent may still be
appending to them. They get scrubbed on the next run.

Remote use (Macs): udragon runs scrub_remote_macs.sh, which copies this
script to each Mac and pipes the merged secrets list (from --print-creds) over
SSH into --creds-stdin. The list is never written to disk on the Macs, and the
Macs do not read any .env files.

Options:
  --creds-stdin   read "secret:placeholder" lines from stdin (used on Macs)
  --print-creds   print the merged "secret:placeholder" list and exit
                  (contains real secrets: pipe it, never log it)
  --dry-run       report what would change without writing any file

Exit code is 0 unless no credentials were found at all.
"""

import glob
import pathlib
import re
import sys
import time

HOME = pathlib.Path.home()
CREDS_FILE = HOME / ".claude/scrub-credentials.txt"
ACTIVE_WINDOW_SECONDS = 600

ENV_GLOBS = [
    "/srv/containers/edq/.env",
    "/srv/containers/edq/docker/*/.env",
]
ENV_MIN_LENGTH = 8
# Key names that mark a value as secret / names that mark it as not secret.
# STRONG names always count; the weaker KEY/URI/DSN names count unless the key
# also looks like a URL/host/user/port setting.
ENV_STRONG_KEY = re.compile(r"(PASS|SECRET|TOKEN|CREDENTIAL)", re.I)
ENV_SECRET_KEY = re.compile(r"(KEY|URI|DSN)", re.I)
ENV_NOT_SECRET_KEY = re.compile(
    r"(URL|HOST|USER|PORT|ENDPOINT|REGION|SSID|PROJECT|HTML|PATH|DIR)", re.I
)

# (label, root, glob patterns, sub-paths to exclude)
TARGETS = [
    ("claude",      HOME / ".claude/projects",               ["**/*.jsonl"], []),
    ("codex",       HOME / ".codex/sessions",                ["**/*.jsonl", "**/*.json"], []),
    ("codex",       HOME / ".codex",                         ["*.jsonl"], []),
    ("gemini",      HOME / ".gemini/tmp",                    ["**/*.json"], []),
    ("antigravity", HOME / ".gemini/antigravity/brain",      ["**/*.json", "**/*.md"], []),
    ("opencode",    HOME / ".local/share/opencode/storage",  ["**/*.json"], []),
    ("grok",        HOME / ".grok",                          ["**/*.json", "**/*.jsonl"], []),
    ("kimi",        HOME / ".kimi-work",                     ["**/*.json", "**/*.jsonl"], ["bin"]),
    ("hermes",      HOME / ".hermes",                        ["**/*.json", "**/*.jsonl"], []),
]

DB_SUFFIXES = {".db", ".sqlite", ".sqlite3"}


def parse_pairs(raw):
    """Parse "secret:placeholder" lines. Placeholders never contain ':', so
    split on the LAST colon; that lets a secret (e.g. a URI) contain colons."""
    pairs = {}
    for line in raw.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and ":" in line:
            secret, placeholder = line.rsplit(":", 1)
            if secret:
                pairs[secret] = placeholder
    return pairs


def collect_env_pairs():
    """Secret values from the .env files, mapped to '<KEY-redacted>'."""
    pairs = {}
    for pattern in ENV_GLOBS:
        for path in sorted(glob.glob(pattern)):
            try:
                text = pathlib.Path(path).read_text(errors="replace")
            except OSError:
                continue
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                if line.startswith("export "):
                    line = line[len("export "):].lstrip()
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                    value = value[1:-1]
                else:
                    value = re.split(r"\s+#", value, maxsplit=1)[0].strip()
                if ENV_STRONG_KEY.search(key):
                    pass  # PASS/SECRET/TOKEN/CREDENTIAL always count (e.g. SFTP_PASS, SUPERUSER_PASSWORD)
                elif not ENV_SECRET_KEY.search(key) or ENV_NOT_SECRET_KEY.search(key):
                    continue
                if len(value) < ENV_MIN_LENGTH or re.search(r"\s", value):
                    continue
                if value.lower() in ("true", "false", "changeme", "password"):
                    continue
                pairs.setdefault(value, f"<{key}-redacted>")
    return pairs


def load_replacements(from_stdin=False):
    if from_stdin:
        pairs = parse_pairs(sys.stdin.read())
    else:
        pairs = collect_env_pairs()
        if CREDS_FILE.exists():
            pairs.update(parse_pairs(CREDS_FILE.read_text()))  # hand-kept entries win
    if not pairs:
        print("  ERROR: no credentials found (list file, .env files or stdin); nothing to scrub against")
        sys.exit(1)
    return pairs


def iter_files(root, patterns, excludes):
    seen = set()
    for pattern in patterns:
        for f in root.glob(pattern):
            if f in seen or not f.is_file() or f.is_symlink():
                continue
            rel = f.relative_to(root).parts
            if rel and rel[0] in excludes:
                continue
            seen.add(f)
            yield f


def main():
    args = sys.argv[1:]
    replacements = load_replacements(from_stdin="--creds-stdin" in args)

    if "--print-creds" in args:
        for secret, placeholder in replacements.items():
            print(f"{secret}:{placeholder}")
        return

    dry_run = "--dry-run" in args
    # Longest first, so a secret that contains another is replaced whole.
    ordered = sorted(replacements.items(), key=lambda kv: len(kv[0]), reverse=True)

    now = time.time()
    totals = {}
    per_placeholder = {}
    skipped_active = 0
    skipped_db = []

    for label, root, patterns, excludes in TARGETS:
        if not root.is_dir():
            continue
        stats = totals.setdefault(label, [0, 0, 0])  # scanned, changed, replacements
        for f in iter_files(root, patterns, excludes):
            try:
                if now - f.stat().st_mtime < ACTIVE_WINDOW_SECONDS:
                    skipped_active += 1
                    continue
                stats[0] += 1
                text = f.read_text(errors="replace")
                new_text = text
                for secret, placeholder in ordered:
                    count = new_text.count(secret)
                    if count:
                        stats[2] += count
                        per_placeholder[placeholder] = per_placeholder.get(placeholder, 0) + count
                        new_text = new_text.replace(secret, placeholder)
                if new_text != text:
                    stats[1] += 1
                    if not dry_run:
                        # Write in place (same inode) so permissions are kept.
                        f.write_text(new_text)
            except Exception as e:
                print(f"  Warning: could not process {f}: {e}")
        for db in root.rglob("*"):
            if db.suffix in DB_SUFFIXES and db.is_file():
                skipped_db.append(db)

    # Databases sitting next to a storage/ root (OpenCode keeps opencode.db one level up)
    for extra in [HOME / ".local/share/opencode"]:
        if extra.is_dir():
            skipped_db.extend(p for p in extra.glob("*") if p.suffix in DB_SUFFIXES and p.is_file())

    mode = "DRY RUN (nothing written)" if dry_run else "scrubbed"
    print(f"  {len(replacements)} secret(s) loaded; {mode}")
    for label, (scanned, changed, count) in totals.items():
        print(f"  {label:12} scanned {scanned:5}  changed {changed:4}  replacements {count}")
    for placeholder, count in sorted(per_placeholder.items(), key=lambda kv: -kv[1]):
        print(f"    {count:6} x {placeholder}")
    if skipped_active:
        print(f"  skipped {skipped_active} file(s) still being written (next run will cover them)")
    for db in sorted(set(skipped_db)):
        print(f"  skipped database (not safe to rewrite): {db}")


if __name__ == "__main__":
    main()
