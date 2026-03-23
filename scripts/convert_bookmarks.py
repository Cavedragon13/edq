#!/usr/bin/env python3
"""
convert_bookmarks.py — Phase 2 of bookmark centralization

Reads all backed-up bookmark files and produces:
  - merged_bookmarks.html  (Netscape HTML, folder structure preserved)
  - dedup_report.txt       (all duplicate URLs that were removed)

Usage:
  python3 scripts/convert_bookmarks.py [BACKUP_DIR]

  BACKUP_DIR defaults to the most recent dated dir in
  /srv/containers/edq/media/bookmark_backups/
"""

import sys
import json
import html
import plistlib
import urllib.parse
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


BACKUP_BASE = Path("/srv/containers/edq/media/bookmark_backups")


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class Bookmark:
    url: str
    title: str
    folder_path: str  # e.g. "Chrome - udragon/Bookmarks bar/Bills"

@dataclass
class Folder:
    name: str
    children: list = field(default_factory=list)  # list of Folder | Bookmark


# ── Chrome / Edge JSON parser ─────────────────────────────────────────────────

def parse_chrome_json(path: Path, source_label: str) -> Folder:
    """Parse a Chrome or Edge Bookmarks JSON file into a Folder tree."""
    with open(path) as f:
        data = json.load(f)

    root_folder = Folder(name=source_label)
    roots = data.get("roots", {})

    root_map = {
        "bookmark_bar": "Bookmarks Bar",
        "other": "Other Bookmarks",
        "synced": "Mobile Bookmarks",
    }

    for key, display_name in root_map.items():
        if key in roots:
            node = roots[key]
            children = node.get("children", [])
            if children:
                sub = _walk_chrome(node, display_name)
                if sub.children:
                    root_folder.children.append(sub)

    return root_folder


def _walk_chrome(node: dict, name: str) -> Folder:
    folder = Folder(name=name)
    for child in node.get("children", []):
        if child.get("type") == "folder":
            sub = _walk_chrome(child, child.get("name", "Unnamed Folder"))
            if sub.children:  # skip empty folders
                folder.children.append(sub)
        elif child.get("type") == "url":
            url = child.get("url", "").strip()
            title = child.get("name", "").strip() or url
            if url and not url.startswith("javascript:"):
                folder.children.append(Bookmark(url=url, title=title, folder_path=""))
    return folder


# ── Safari plist parser ───────────────────────────────────────────────────────

def parse_safari_plist(path: Path, source_label: str = "Safari") -> Folder:
    """Parse a Safari Bookmarks.plist into a Folder tree."""
    with open(path, "rb") as f:
        data = plistlib.load(f)

    root_folder = Folder(name=source_label)

    # Top-level Children: History (skip), BookmarksBar, BookmarksMenu, ReadingList (skip)
    for child in data.get("Children", []):
        btype = child.get("WebBookmarkType", "")
        title = child.get("Title", "")
        if btype == "WebBookmarkTypeProxy":
            continue  # History
        if title == "com.apple.ReadingList":
            continue  # Reading list — not real bookmarks
        if btype == "WebBookmarkTypeList":
            display = "Bookmarks Bar" if title == "BookmarksBar" else title
            sub = _walk_safari(child, display)
            if sub.children:
                root_folder.children.append(sub)

    return root_folder


def _walk_safari(node: dict, name: str) -> Folder:
    folder = Folder(name=name)
    for child in node.get("Children", []):
        btype = child.get("WebBookmarkType", "")
        if btype == "WebBookmarkTypeList":
            title = child.get("Title", "Unnamed Folder")
            sub = _walk_safari(child, title)
            if sub.children:
                folder.children.append(sub)
        elif btype == "WebBookmarkTypeLeaf":
            url = child.get("URLString", "").strip()
            uri_dict = child.get("URIDictionary", {})
            title = (uri_dict.get("title") or child.get("Title") or "").strip() or url
            if url and not url.startswith("javascript:"):
                folder.children.append(Bookmark(url=url, title=title, folder_path=""))
    return folder


# ── Deduplication ─────────────────────────────────────────────────────────────

def _normalize_url(url: str) -> str:
    """Normalize a URL for deduplication (lowercase scheme+host, strip trailing /)."""
    try:
        parsed = urllib.parse.urlparse(url)
        normalized = parsed._replace(
            scheme=parsed.scheme.lower(),
            netloc=parsed.netloc.lower(),
        )
        result = urllib.parse.urlunparse(normalized)
        return result.rstrip("/")
    except Exception:
        return url.strip().rstrip("/")


def deduplicate_tree(root: Folder) -> tuple[Folder, list[tuple[str, str, str]]]:
    """
    Walk the entire tree, removing bookmarks whose URLs have already been seen.
    Returns (new_root, duplicates) where duplicates is a list of (url, title, location).
    The first occurrence of each URL wins (depth-first, left-to-right).
    """
    seen: dict[str, str] = {}  # normalized_url -> "folder/path"
    duplicates: list[tuple[str, str, str]] = []

    def walk(node: Folder, path: str) -> Folder:
        new_children = []
        for child in node.children:
            if isinstance(child, Folder):
                sub = walk(child, f"{path}/{child.name}")
                if sub.children:
                    new_children.append(sub)
            elif isinstance(child, Bookmark):
                key = _normalize_url(child.url)
                if key in seen:
                    duplicates.append((child.url, child.title, f"{path} (dup of {seen[key]})"))
                else:
                    seen[key] = f"{path}"
                    child.folder_path = path
                    new_children.append(child)
        node.children = new_children
        return node

    deduped = walk(root, root.name)
    return deduped, duplicates


# ── Netscape HTML writer ──────────────────────────────────────────────────────

NETSCAPE_HEADER = """<!DOCTYPE NETSCAPE-Bookmark-file-1>
<!-- This is an automatically generated file.
     It will be read and overwritten.
     DO NOT EDIT! -->
<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">
<TITLE>Bookmarks</TITLE>
<H1>Bookmarks</H1>
<DL><p>
"""

NETSCAPE_FOOTER = "</DL><p>\n"


def write_netscape_html(root: Folder, out_path: Path) -> int:
    """Write a Folder tree as Netscape HTML. Returns total bookmark count."""
    count = [0]

    def write_folder(f: Folder, lines: list, indent: int):
        pad = "    " * indent
        lines.append(f'{pad}<DT><H3>{html.escape(f.name)}</H3>')
        lines.append(f'{pad}<DL><p>')
        for child in f.children:
            if isinstance(child, Folder):
                write_folder(child, lines, indent + 1)
            elif isinstance(child, Bookmark):
                title = html.escape(child.title or child.url)
                url = html.escape(child.url)
                lines.append(f'{pad}    <DT><A HREF="{url}">{title}</A>')
                count[0] += 1
        lines.append(f'{pad}</DL><p>')

    lines = [NETSCAPE_HEADER.rstrip("\n")]
    for child in root.children:
        if isinstance(child, Folder):
            write_folder(child, lines, 1)
    lines.append(NETSCAPE_FOOTER.rstrip("\n"))

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return count[0]


# ── Main ──────────────────────────────────────────────────────────────────────

def find_backup_dir(arg: Optional[str] = None) -> Path:
    if arg:
        p = Path(arg)
        if not p.exists():
            sys.exit(f"[!] Backup dir not found: {p}")
        return p
    # Find most recent dated subdir
    dirs = sorted(BACKUP_BASE.glob("????-??-??"), reverse=True)
    if not dirs:
        sys.exit(f"[!] No backup dirs found in {BACKUP_BASE}")
    return dirs[0]


def main():
    backup_dir = find_backup_dir(sys.argv[1] if len(sys.argv) > 1 else None)
    print(f"[*] Reading from: {backup_dir}")
    print()

    # Master root that holds one sub-folder per source
    master = Folder(name="Bookmarks")

    # Source definitions: (file, parser_fn, label)
    sources = [
        ("udragon_chrome_Bookmarks",  parse_chrome_json,  "Chrome - udragon"),
        ("odragon_chrome_Bookmarks",  parse_chrome_json,  "Chrome - odragon"),
        ("adragon_chrome_Bookmarks",  parse_chrome_json,  "Chrome - adragon"),
        ("cdragon_chrome_Bookmarks",  parse_chrome_json,  "Chrome - cdragon"),
        ("cdragon_edge_Bookmarks",    parse_chrome_json,  "Edge - cdragon"),
        ("safari_Bookmarks.plist",    parse_safari_plist, "Safari"),
    ]

    for filename, parser, label in sources:
        fpath = backup_dir / filename
        if not fpath.exists():
            print(f"[!] Missing: {filename} — skipping")
            continue
        try:
            folder = parser(fpath, label)
            bcount = sum(1 for _ in _iter_bookmarks(folder))
            print(f"[+] {label}: {bcount} bookmarks parsed")
            if folder.children:
                master.children.append(folder)
        except Exception as e:
            print(f"[!] Failed to parse {filename}: {e}")

    print()
    total_before = sum(1 for _ in _iter_bookmarks(master))
    print(f"[*] Total before dedup: {total_before}")

    master, duplicates = deduplicate_tree(master)
    total_after = sum(1 for _ in _iter_bookmarks(master))
    print(f"[*] Duplicates removed: {len(duplicates)}")
    print(f"[*] Total after dedup:  {total_after}")
    print()

    # Write merged HTML
    out_html = backup_dir / "merged_bookmarks.html"
    count = write_netscape_html(master, out_html)
    print(f"[✓] Wrote {count} bookmarks → {out_html}")

    # Write dedup report
    out_report = backup_dir / "dedup_report.txt"
    with open(out_report, "w") as f:
        f.write(f"Deduplication Report — {backup_dir.name}\n")
        f.write(f"Removed {len(duplicates)} duplicate URL(s)\n\n")
        for url, title, location in duplicates:
            f.write(f"URL:      {url}\n")
            f.write(f"Title:    {title}\n")
            f.write(f"Location: {location}\n\n")
    print(f"[✓] Dedup report → {out_report}")


def _iter_bookmarks(node):
    """Yield all Bookmark objects in a tree."""
    for child in node.children:
        if isinstance(child, Folder):
            yield from _iter_bookmarks(child)
        elif isinstance(child, Bookmark):
            yield child


if __name__ == "__main__":
    main()
