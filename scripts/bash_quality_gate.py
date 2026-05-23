#!/usr/bin/env python3
"""
PreToolUse hook: catches shell code quality issues before execution.
Blocks commands that would trigger Claude Code's built-in safety dialogs.
Exits 2 (block + feedback) if problems found, 0 to allow.
"""
import json
import re
import sys


def check(cmd: str) -> list[str]:
    errors = []

    # Pattern 1: # comment inside a double-quoted multiline argument
    # e.g.  ssh host "\n# comment\n..."
    # Claude Code flags this as "Newline followed by # inside a quoted argument"
    if re.search(r'"[^"]*\n[ \t]*#', cmd):
        errors.append(
            'Remove # comments from inside double-quoted arguments '
            '(e.g. ssh "...\\n# comment..."). '
            'Put explanations in the Bash tool description field instead.'
        )

    # Pattern 2: simple (unquoted) variable expansion outside of quotes
    # Matches $VARNAME or $varname not preceded by " or preceded by a ${ or $(
    # Heuristic: look for $[A-Za-z_] not inside "..." or '...'
    # Strip quoted sections first to avoid false positives inside strings
    stripped = re.sub(r'"[^"]*"', '""', cmd)   # collapse double-quoted regions
    stripped = re.sub(r"'[^']*'", "''", stripped)  # collapse single-quoted regions
    if re.search(r'(?<!\$)\$(?!\(|\{)[A-Za-z_][A-Za-z0-9_]*', stripped):
        errors.append(
            'Unquoted variable expansion: use "$VAR" not $VAR '
            '(triggers "Contains simple_expansion" safety dialog).'
        )

    return errors


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    if data.get('tool_name') != 'Bash':
        sys.exit(0)

    cmd = data.get('tool_input', {}).get('command', '')
    if not cmd:
        sys.exit(0)

    errors = check(cmd)
    if errors:
        print('Shell quality gate — fix before retrying:', file=sys.stderr)
        for e in errors:
            print(f'  • {e}', file=sys.stderr)
        sys.exit(2)

    sys.exit(0)


if __name__ == '__main__':
    main()
