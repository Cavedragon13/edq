#!/usr/bin/env python3
"""
KB Compiler — Karpathy-style knowledge base pipeline.

Delta-based: processes only new/changed inputs since last run.

Input sources:
  1. knowledge-base/raw/       — manually dropped docs (any .md or .txt)
  2. knowledge-base/Add to Tools.md — plain (non-struck-through) URLs
  3. knowledge-base/Daily Notes/    — notes newer than last_run date

Output: knowledge-base/KB/ wiki articles + KB/index.md
LLM: local Ollama (model configurable via --model flag or OLLAMA_MODEL env var)
"""

import argparse
import datetime
import hashlib
import html.parser
import json
import pathlib
import os
import re
import sys
import textwrap
import time
import urllib.request
import urllib.error

sys.path.insert(0, '/srv/containers/edq')
from scripts import provider_models

# ── Paths ───────────────────────────────────────────────────────────────────
KB_BASE      = pathlib.Path.home() / "knowledge-base"
RAW_DIR      = KB_BASE / "raw"
KB_DIR       = KB_BASE / "KB"
STATE_FILE   = RAW_DIR / ".state.json"
ADD_TO_TOOLS = KB_BASE / "Add to Tools.md"
DAILY_NOTES  = KB_BASE / "Daily Notes"

OLLAMA_URL   = os.getenv('OLLAMA_URL', 'http://localhost:11434') + '/api/generate'
DEFAULT_MODEL = os.getenv('OLLAMA_MODEL', 'gemma4:e4b')

def resolve_ollama_model(preferred: str | None = None) -> str:
    preferred = preferred or os.environ.get('OLLAMA_MODEL') or DEFAULT_MODEL
    return provider_models.resolve_model('ollama', 'analysis', preferred=preferred).get('model') or preferred

# ── State ────────────────────────────────────────────────────────────────────
def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {
        "last_run": None,
        "processed_files": {},   # filename → sha256
        "processed_urls": [],
        "processed_daily_notes": [],
    }

def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))

def file_hash(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]

# ── HTML → plain text ────────────────────────────────────────────────────────
class _TextExtractor(html.parser.HTMLParser):
    SKIP_TAGS = {"script", "style", "noscript", "nav", "footer", "header"}

    def __init__(self):
        super().__init__()
        self._parts = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in self.SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag.lower() in self.SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if not self._skip_depth:
            stripped = data.strip()
            if stripped:
                self._parts.append(stripped)

    def get_text(self) -> str:
        return "\n".join(self._parts)


def html_to_text(html_str: str) -> str:
    parser = _TextExtractor()
    parser.feed(html_str)
    text = parser.get_text()
    # Collapse runs of blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def fetch_url(url: str, timeout: int = 20) -> str | None:
    """Fetch URL and return plain text. Returns None on failure."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (kb-compiler/1.0)"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read().decode("utf-8", errors="replace")
            if "html" in content_type.lower():
                return html_to_text(raw)
            return raw  # plain text / markdown
    except Exception as e:
        print(f"  ⚠ fetch failed for {url}: {e}", file=sys.stderr)
        return None

# ── Ollama ───────────────────────────────────────────────────────────────────
COMPILE_PROMPT = textwrap.dedent("""\
    You are a knowledge base compiler. Convert the source material below into a
    structured Obsidian-flavoured Markdown wiki article.

    Rules:
    - Title: clear and searchable (## heading level 1)
    - Summary: 2-3 sentences at the top
    - Use ## headings to organise content into logical sections
    - End with a ## Tags section — 3-6 lowercase hashtags like #tools #ai
    - Preserve specific names, version numbers, URLs, and commands exactly
    - Do NOT invent facts not in the source
    - Return ONLY the article — no preamble, no "Here is the article:" wrapper

    Source material:
    ---
    {content}
    ---
""")

def compile_with_ollama(content: str, model: str, source_label: str) -> str | None:
    """Send content to Ollama and return compiled article text."""
    # Truncate very long inputs to avoid context overflow (keep first 6000 chars)
    if len(content) > 6000:
        content = content[:6000] + "\n\n[... truncated for length ...]"

    prompt = COMPILE_PROMPT.format(content=content)
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": True,
        "options": {"temperature": 0.3, "num_predict": 1200},
    }).encode()

    print(f"  🧠 Compiling: {source_label} ...", end="", flush=True)
    try:
        req = urllib.request.Request(
            OLLAMA_URL, data=payload,
            headers={"Content-Type": "application/json"}, method="POST"
        )
        parts = []
        with urllib.request.urlopen(req, timeout=120) as resp:
            for line in resp:
                line = line.strip()
                if not line:
                    continue
                chunk = json.loads(line)
                parts.append(chunk.get("response", ""))
                if chunk.get("done"):
                    break
        print(" done")
        return "".join(parts).strip()
    except Exception as e:
        print(f" FAILED: {e}", file=sys.stderr)
        return None

# ── Article saving ────────────────────────────────────────────────────────────
def slug(title: str) -> str:
    s = title.lower()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"\s+", "-", s.strip())
    return s[:80] or "untitled"

def extract_title(article: str) -> str:
    """Pull first # heading from article, fallback to first line."""
    for line in article.splitlines():
        line = line.strip()
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return article.splitlines()[0][:60] if article else "Untitled"

def save_article(article: str, source_label: str) -> pathlib.Path:
    """Write article to KB/ and return the path."""
    KB_DIR.mkdir(parents=True, exist_ok=True)
    title = extract_title(article)
    filename = slug(title) + ".md"
    dest = KB_DIR / filename

    # Prepend metadata comment if not already a # heading
    if not article.lstrip().startswith("#"):
        article = f"# {title}\n\n{article}"

    # Append source provenance if not already present
    today = datetime.date.today().isoformat()
    if "source:" not in article.lower():
        article += f"\n\n---\n_Compiled {today} from: {source_label}_\n"

    dest.write_text(article)
    return dest

# ── Index maintenance ─────────────────────────────────────────────────────────
def rebuild_index():
    articles = sorted(KB_DIR.glob("*.md"))
    articles = [a for a in articles if a.name != "index.md"]
    lines = [
        "# KB Index",
        "",
        f"_Last updated: {datetime.date.today().isoformat()} — {len(articles)} articles_",
        "",
    ]
    for path in articles:
        content = path.read_text()
        title = extract_title(content)
        lines.append(f"- [[{path.stem}|{title}]]")

    (KB_DIR / "index.md").write_text("\n".join(lines) + "\n")
    print(f"  📑 Index updated ({len(articles)} articles)")

# ── Input source 1: raw/ files ────────────────────────────────────────────────
def process_raw_files(state: dict, model: str, dry_run: bool) -> int:
    count = 0
    for path in sorted(RAW_DIR.glob("*.md")) + sorted(RAW_DIR.glob("*.txt")):
        if path.name.startswith("."):
            continue
        h = file_hash(path)
        if state["processed_files"].get(path.name) == h:
            continue  # unchanged
        print(f"\n📄 Raw file: {path.name}")
        content = path.read_text()
        if not dry_run:
            article = compile_with_ollama(content, model, path.name)
            if article:
                dest = save_article(article, f"raw/{path.name}")
                print(f"  ✅ Saved → {dest.name}")
                state["processed_files"][path.name] = h
                count += 1
        else:
            print(f"  [dry-run] would compile {len(content)} chars")
            state["processed_files"][path.name] = h
            count += 1
    return count

# ── Input source 2: Add to Tools.md URLs ─────────────────────────────────────
URL_RE = re.compile(r"https?://[^\s\)\]>]+")

def extract_unprocessed_urls(tools_file: pathlib.Path, already_done: list[str]) -> list[str]:
    """Return plain (non-struck-through) URLs not yet processed."""
    urls = []
    for line in tools_file.read_text().splitlines():
        # Skip struck-through lines (~~...~~)
        if "~~" in line:
            continue
        for url in URL_RE.findall(line):
            if url not in already_done:
                urls.append(url)
    return urls

def process_urls(state: dict, model: str, dry_run: bool) -> int:
    if not ADD_TO_TOOLS.exists():
        return 0
    urls = extract_unprocessed_urls(ADD_TO_TOOLS, state["processed_urls"])
    count = 0
    for url in urls:
        print(f"\n🔗 URL: {url}")
        if not dry_run:
            text = fetch_url(url)
            if not text:
                continue
            article = compile_with_ollama(text, model, url)
            if article:
                dest = save_article(article, url)
                print(f"  ✅ Saved → {dest.name}")
                state["processed_urls"].append(url)
                count += 1
        else:
            print(f"  [dry-run] would fetch and compile")
            state["processed_urls"].append(url)
            count += 1
    return count

# ── Input source 3: Daily Notes delta ────────────────────────────────────────
def process_daily_notes(state: dict, model: str, dry_run: bool) -> int:
    if not DAILY_NOTES.exists():
        return 0
    done = set(state["processed_daily_notes"])
    count = 0
    for path in sorted(DAILY_NOTES.glob("*.md")):
        stem = path.stem  # e.g. "2026-04-04"
        if stem in done:
            continue
        # Only process notes from before today (complete notes)
        try:
            note_date = datetime.date.fromisoformat(stem)
        except ValueError:
            continue
        if note_date >= datetime.date.today():
            continue
        print(f"\n📅 Daily note: {stem}")
        content = path.read_text()
        if not dry_run:
            article = compile_with_ollama(content, model, f"Daily Notes/{stem}")
            if article:
                dest = save_article(article, f"Daily Notes/{stem}.md")
                print(f"  ✅ Saved → {dest.name}")
                state["processed_daily_notes"].append(stem)
                count += 1
        else:
            print(f"  [dry-run] would compile {len(content)} chars")
            state["processed_daily_notes"].append(stem)
            count += 1
    return count

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="KB Compiler — Karpathy-style knowledge base pipeline")
    parser.add_argument("--model", default=None, help="Ollama model name (default: OLLAMA_MODEL env or gemma4:e4b)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be processed without calling Ollama")
    parser.add_argument("--reprocess", metavar="FILE", help="Force-reprocess a specific raw/ filename or 'all'")
    parser.add_argument("--source", choices=["raw", "urls", "notes", "all"], default="all",
                        help="Which input source to process (default: all)")
    args = parser.parse_args()

    model = resolve_ollama_model(args.model)

    state = load_state()

    if args.reprocess:
        if args.reprocess == "all":
            state["processed_files"] = {}
            print("🔄 Cleared all processed file state — will reprocess everything")
        else:
            state["processed_files"].pop(args.reprocess, None)
            print(f"🔄 Cleared state for {args.reprocess}")

    print(f"🐉 KB Compiler — model: {model} | dry-run: {args.dry_run}")
    print(f"   Last run: {state['last_run'] or 'never'}")

    total = 0
    if args.source in ("raw", "all"):
        total += process_raw_files(state, model, args.dry_run)
    if args.source in ("urls", "all"):
        total += process_urls(state, model, args.dry_run)
    if args.source in ("notes", "all"):
        total += process_daily_notes(state, model, args.dry_run)

    if total > 0 and not args.dry_run:
        rebuild_index()

    state["last_run"] = datetime.date.today().isoformat()
    if not args.dry_run:
        save_state(state)

    print(f"\n✅ KB Compiler done — {total} new articles compiled")

if __name__ == "__main__":
    main()
