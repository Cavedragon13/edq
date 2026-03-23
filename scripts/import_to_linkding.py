#!/usr/bin/env python3
"""
import_to_linkding.py — Phase 4 of bookmark centralization

Reads merged_bookmarks.html (Netscape format) from the backup dir,
parses the folder hierarchy, and imports every bookmark into Linkding
via REST API with folder-path tags.

Tags created per bookmark:
  - Full path tag:  "Chrome - udragon/Bookmarks Bar/Bills"
  - Parent tags:    "Chrome - udragon/Bookmarks Bar", "Chrome - udragon"
  → Allows filtering by any level of the hierarchy

Usage:
  python3 scripts/import_to_linkding.py [MERGED_HTML] [API_TOKEN]

  Defaults:
    MERGED_HTML = most recent backup dir / merged_bookmarks.html
    API_TOKEN   = $LINKDING_API_TOKEN from .env, or /srv/containers/edq/.env
"""

import sys
import os
import re
import time
import urllib.request
import urllib.error
import json
from pathlib import Path
from html.parser import HTMLParser
try:
    from dotenv import load_dotenv  # type: ignore
except ImportError:
    def load_dotenv(path=None): pass


LINKDING_URL = "http://localhost:8039"
BACKUP_BASE = Path("/srv/containers/edq/media/bookmark_backups")
ENV_FILE = Path("/srv/containers/edq/.env")


# ── Netscape HTML parser ──────────────────────────────────────────────────────

class BookmarkHTMLParser(HTMLParser):
    """Parse Netscape bookmark HTML into (url, title, folder_path) tuples."""

    def __init__(self):
        super().__init__()
        self.results: list[tuple[str, str, str]] = []
        self._folder_stack: list[str] = []
        self._in_anchor = False
        self._current_url = ""
        self._current_title = ""
        self._in_h3 = False
        self._current_h3 = ""

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "a":
            self._in_anchor = True
            self._current_url = attrs_dict.get("href", "").strip()
            self._current_title = ""
        elif tag == "h3":
            self._in_h3 = True
            self._current_h3 = ""
        elif tag == "dl":
            # Entering a sub-list — push the last H3 we saw as a folder
            if self._current_h3:
                self._folder_stack.append(self._current_h3)
                self._current_h3 = ""

    def handle_endtag(self, tag):
        if tag == "a" and self._in_anchor:
            self._in_anchor = False
            if self._current_url:
                path = "/".join(self._folder_stack) if self._folder_stack else ""
                self.results.append((self._current_url, self._current_title.strip(), path))
        elif tag == "h3":
            self._in_h3 = False
        elif tag == "dl":
            if self._folder_stack:
                self._folder_stack.pop()

    def handle_data(self, data):
        if self._in_anchor:
            self._current_title += data
        elif self._in_h3:
            self._current_h3 += data


# ── Linkding API ──────────────────────────────────────────────────────────────

def api_create_bookmark(url_base: str, token: str, bm_url: str, title: str, tags: list[str]) -> tuple[str, int]:
    """
    POST to Linkding API to create a bookmark.
    Returns (status, http_code): status is 'created', 'duplicate', or 'error'.
    """
    payload = json.dumps({
        "url": bm_url,
        "title": title,
        "tag_names": tags,
        "is_archived": False,
        "unread": False,
        "shared": False,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{url_base}/api/bookmarks/",
        data=payload,
        headers={
            "Authorization": f"Token {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return "created", resp.status
    except urllib.error.HTTPError as e:
        if e.code == 400:
            # Could be duplicate URL or validation error — read body
            body = e.read().decode("utf-8", errors="replace")
            if "already exists" in body.lower() or "unique" in body.lower():
                return "duplicate", 400
            return f"error: {body[:120]}", 400
        return f"error: HTTP {e.code}", e.code
    except Exception as ex:
        return f"error: {ex}", 0


def build_tags(folder_path: str) -> list[str]:
    """Build tag list from folder path: full path + all ancestor paths."""
    if not folder_path:
        return []
    parts = folder_path.split("/")
    tags = []
    for i in range(len(parts)):
        tag = "/".join(parts[: i + 1])
        tags.append(tag)
    return tags


# ── Main ──────────────────────────────────────────────────────────────────────

def find_merged_html(arg: str | None = None) -> Path:
    if arg:
        p = Path(arg)
        if not p.exists():
            sys.exit(f"[!] Not found: {p}")
        return p
    dirs = sorted(BACKUP_BASE.glob("????-??-??"), reverse=True)
    if not dirs:
        sys.exit(f"[!] No backup dirs in {BACKUP_BASE}")
    candidate = dirs[0] / "merged_bookmarks.html"
    if not candidate.exists():
        sys.exit(f"[!] No merged_bookmarks.html in {dirs[0]}")
    return candidate


def main():
    # Load env
    load_dotenv(ENV_FILE)

    merged_html = find_merged_html(sys.argv[1] if len(sys.argv) > 1 else None)
    api_token = sys.argv[2] if len(sys.argv) > 2 else os.getenv("LINKDING_API_TOKEN", "")
    if not api_token:
        sys.exit("[!] No API token — set LINKDING_API_TOKEN in .env or pass as second arg")

    print(f"[*] Source: {merged_html}")
    print(f"[*] Target: {LINKDING_URL}")
    print()

    # Parse HTML
    html_text = merged_html.read_text(encoding="utf-8")
    parser = BookmarkHTMLParser()
    parser.feed(html_text)
    bookmarks = parser.results
    print(f"[*] Parsed {len(bookmarks)} bookmarks from HTML")
    print()

    # Skip the top-level "Bookmarks" folder name that's embedded in every path
    # (the root folder emits an H3 "Bookmarks" which becomes the first path component
    #  for all children — strip it if present)
    cleaned = []
    for url, title, path in bookmarks:
        # Strip leading "Bookmarks/" from path if present
        if path.startswith("Bookmarks/"):
            path = path[len("Bookmarks/"):]
        elif path == "Bookmarks":
            path = ""
        cleaned.append((url, title, path))
    bookmarks = cleaned

    # Import
    n_created = 0
    n_duplicate = 0
    n_error = 0
    errors: list[tuple[str, str]] = []

    for i, (bm_url, title, folder_path) in enumerate(bookmarks, 1):
        tags = build_tags(folder_path)
        status, code = api_create_bookmark(LINKDING_URL, api_token, bm_url, title, tags)

        if status == "created":
            n_created += 1
        elif status == "duplicate":
            n_duplicate += 1
        else:
            n_error += 1
            errors.append((bm_url, status))

        if i % 50 == 0 or i == len(bookmarks):
            pct = i / len(bookmarks) * 100
            print(f"  [{i:4d}/{len(bookmarks)}] {pct:5.1f}%  created={n_created}  dup={n_duplicate}  err={n_error}")

        # Small pause to avoid overwhelming the server
        if i % 100 == 0:
            time.sleep(0.2)

    print()
    print(f"[✓] Import complete:")
    print(f"    Created:    {n_created}")
    print(f"    Duplicates: {n_duplicate}")
    print(f"    Errors:     {n_error}")

    if errors:
        print()
        print("[!] Errors:")
        for url, msg in errors[:20]:
            print(f"    {url[:70]}")
            print(f"    -> {msg}")
        if len(errors) > 20:
            print(f"    ... and {len(errors) - 20} more")


if __name__ == "__main__":
    main()
