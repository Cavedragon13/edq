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

    # Pattern 3: heredocs — any << 'TAG' / <<TAG / <<- 'TAG' variant.
    # Exception: `git commit -m "$(cat <<'EOF' ... EOF)"` is the harness's own
    # mandated commit-message idiom (see system prompt) — don't block that one.
    if re.search(r'<<[-~]?\s*[\'"]?\w+', cmd) and 'git commit' not in cmd:
        errors.append(
            'Heredocs are not allowed (triggers the quoted-argument safety dialog '
            'every time). Use the Write tool to create the file instead.'
        )

    # Pattern 4: for/while loops
    if re.search(r'\bfor\s+\w+\s+in\b', cmd, re.DOTALL) or re.search(r'\bwhile\b.*?\bdo\b', cmd, re.DOTALL):
        errors.append(
            'for/while loops trigger the safety dialog on their own, even with '
            'every variable quoted correctly. Fold the loop into a single command '
            '(e.g. one grep -e per term) or write it to a script file instead.'
        )

    # Pattern 5: arithmetic expansion referencing a variable (not a pure literal)
    for m in re.finditer(r'\$\(\(([^)]*)\)\)', cmd):
        if re.search(r'(?<!\$)\b[A-Za-z_][A-Za-z0-9_]*\b', m.group(1)):
            errors.append(
                'Arithmetic expansion $((...)) references a variable/name, not a pure '
                'literal — triggers the safety dialog. Compute the value first (e.g. '
                '`date -d "N days ago" +%s`) or do the arithmetic in a script file.'
            )
            break

    # Pattern 6: source / . (dot) command — even just for venv activation
    if re.search(r'(^|[;&|\n]|&&|\|\|)\s*(source|\.)\s+\S', cmd):
        errors.append(
            "'source' (or '.') triggers \"evaluates arguments as shell code\". "
            'For venv activation, call the venv\'s own interpreter directly '
            '(venv/bin/python3 script.py) instead of sourcing activate.'
        )

    # Pattern 7: command substitution $(...) — including var=$(...) patterns.
    # Exception: same git-commit heredoc idiom as pattern 3 — "$(cat <<'EOF' ...)"
    # is the harness's mandated commit-message wrapper, not a real substitution.
    if re.search(r'\$\([^)]', cmd) and 'git commit' not in cmd:
        errors.append(
            'Command substitution $(...) triggers "cannot be statically analyzed" '
            '(this includes `VAR=$(cmd)` assignments later interpolated into the '
            'same command). Write the logic to a script file instead.'
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
