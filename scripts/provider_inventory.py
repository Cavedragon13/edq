#!/usr/bin/env python3
"""Inventory first-party Dragonsuite files that reference provider APIs/models."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path('/srv/containers/edq')
SCAN_ROOTS = [ROOT / 'scripts', ROOT / 'projects' / 'coversynth-openai', ROOT / 'projects' / 'coversynth-json']
SKIP_PARTS = {'node_modules', '__pycache__'}
SKIP_PREFIXES = ('venv', '.venv')
EXTS = {'.py', '.js', '.ts', '.tsx', '.html', '.sh', '.md'}
PATTERNS = {
    'openai': re.compile(r'OPENAI_API_KEY|gpt-[0-9a-zA-Z._-]+|gpt-image-[0-9a-zA-Z._-]+|dall-e-[0-9]+'),
    'google': re.compile(r'GOOGLE_API_KEY|GEMINI_API_KEY|gemini-[0-9a-zA-Z._-]+|imagen-[0-9a-zA-Z._-]+|veo-[0-9a-zA-Z._-]+|lyria-[0-9a-zA-Z._/-]+'),
    'anthropic': re.compile(r'ANTHROPIC_API_KEY|claude-[0-9a-zA-Z._-]+'),
    'openrouter': re.compile(r'OPENROUTER_API_KEY|openrouter', re.I),
    'ollama': re.compile(r'OLLAMA|/api/tags|/api/generate|/api/chat'),
    'local_openai': re.compile(r'LM_STUDIO|LLAMACPP|llama\.cpp|/v1/models'),
}
MODEL_PATTERN = re.compile(r'(gpt-[0-9][0-9a-zA-Z._-]*|gpt-image-[0-9][0-9a-zA-Z._-]*|gemini-[0-9][0-9a-zA-Z._-]*|imagen-[0-9][0-9a-zA-Z._-]*|veo-[0-9][0-9a-zA-Z._-]*|claude-(?:sonnet|opus|haiku)-[0-9][0-9a-zA-Z._-]*|dall-e-[0-9]+)')


def should_scan(path: Path) -> bool:
    if path.suffix not in EXTS:
        return False
    parts = set(path.parts)
    if parts & SKIP_PARTS:
        return False
    return not any(part.startswith(SKIP_PREFIXES) for part in path.parts)


def files():
    for root in SCAN_ROOTS:
        if root.is_file() and should_scan(root):
            yield root
        elif root.exists():
            for path in root.rglob('*'):
                if path.is_file() and should_scan(path):
                    yield path


def classify(path: Path) -> dict | None:
    try:
        text = path.read_text(errors='replace')
    except Exception:
        return None
    providers = [name for name, pattern in PATTERNS.items() if pattern.search(text)]
    if not providers:
        return None
    models = sorted(set(MODEL_PATTERN.findall(text)))
    category = 'api-call-or-config' if any('API_KEY' in line or 'models.' in line or 'requests.' in line for line in text.splitlines()) else 'reference'
    return {
        'file': str(path.relative_to(ROOT)),
        'providers': providers,
        'models': models,
        'category': category,
    }


def main():
    records = [record for path in files() if (record := classify(path))]
    print(json.dumps({'count': len(records), 'records': records}, indent=2))


if __name__ == '__main__':
    main()
