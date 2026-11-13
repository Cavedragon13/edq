#!/usr/bin/env python3
"""scrub_transcripts.py — replace known secrets in AI agent transcripts.

Reads ~/.claude/scrub-credentials.txt (one "secret:placeholder" per line,
chmod 600) and replaces every literal occurrence of each secret in the
transcript files of every agent found on this machine.

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
script to each Mac and pipes the credentials over SSH into --creds-stdin.
The secrets list is never written to disk on the Macs.

Exit code is 0 unless no credentials were provided.
"""

import pathlib
import sys
import time

HOME = pathlib.Path.home()
CREDS_FILE = HOME / ".claude/scrub-credentials.txt"
ACTIVE_WINDOW_SECONDS = 600

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


def load_replacements(from_stdin=False):
    if from_stdin:
        raw = sys.stdin.read()
    elif CREDS_FILE.exists():
        raw = CREDS_FILE.read_text()
    else:
        print(f"  ERROR: {CREDS_FILE} not found; nothing to scrub against")
        sys.exit(1)
    pairs = {}
    for line in raw.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and ":" in line:
            secret, placeholder = line.split(":", 1)
            if secret:
                pairs[secret] = placeholder
    if not pairs:
        print("  ERROR: no credentials provided; nothing to scrub against")
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
    replacements = load_replacements(from_stdin="--creds-stdin" in sys.argv[1:])
    now = time.time()
    totals = {}
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
                for secret, placeholder in replacements.items():
                    count = new_text.count(secret)
                    if count:
                        stats[2] += count
                        new_text = new_text.replace(secret, placeholder)
                if new_text != text:
                    # Write in place (same inode) so permissions are kept.
                    f.write_text(new_text)
                    stats[1] += 1
            except Exception as e:
                print(f"  Warning: could not process {f}: {e}")
        for db in root.rglob("*"):
            if db.suffix in DB_SUFFIXES and db.is_file():
                skipped_db.append(db)

    # Databases sitting next to a storage/ root (OpenCode keeps opencode.db one level up)
    for extra in [HOME / ".local/share/opencode"]:
        if extra.is_dir():
            skipped_db.extend(p for p in extra.glob("*") if p.suffix in DB_SUFFIXES and p.is_file())

    for label, (scanned, changed, count) in totals.items():
        print(f"  {label:12} scanned {scanned:5}  changed {changed:4}  replacements {count}")
    if skipped_active:
        print(f"  skipped {skipped_active} file(s) still being written (next run will cover them)")
    for db in sorted(set(skipped_db)):
        print(f"  skipped database (not safe to rewrite): {db}")


if __name__ == "__main__":
    main()
