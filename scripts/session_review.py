#!/usr/bin/env python3
"""
Session Review Tool - End-of-session knowledge base update helper

Usage:
    python session_review.py

Creates:
- Obsidian daily note with session summary
- Updates to memory files (if needed)
- Git snapshot of changes
"""

import os
import sys
from pathlib import Path
from datetime import datetime
import subprocess
import json

# Paths
PROJECT_ROOT = Path("/srv/containers/edq")
OBSIDIAN_VAULT = Path.home() / "knowledge-base"
MEMORY_DIR = Path.home() / ".claude/projects/-srv-containers-edq/memory"
DAILY_NOTES_DIR = OBSIDIAN_VAULT / "Daily Notes"
DAILY_NOTES_DIR.mkdir(parents=True, exist_ok=True)

# Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_header(text):
    """Print colored header"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(70)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 70}{Colors.ENDC}\n")


def print_section(text):
    """Print section header"""
    print(f"\n{Colors.OKBLUE}{Colors.BOLD}{text}{Colors.ENDC}")
    print(f"{Colors.OKBLUE}{'-' * len(text)}{Colors.ENDC}")


def get_git_changes():
    """Get git status and recent changes"""
    os.chdir(PROJECT_ROOT)

    # Get status
    status = subprocess.run(
        ["git", "status", "--short"],
        capture_output=True,
        text=True
    ).stdout.strip()

    # Get recent commits (last 5)
    commits = subprocess.run(
        ["git", "log", "-5", "--oneline"],
        capture_output=True,
        text=True
    ).stdout.strip()

    # Get files changed
    files_changed = []
    if status:
        for line in status.split('\n'):
            if line.strip():
                files_changed.append(line.strip())

    return {
        "status": status,
        "commits": commits,
        "files_changed": files_changed
    }


def scan_for_new_services():
    """Check for newly added services in dragonsuite.json"""
    config_path = PROJECT_ROOT / "config/dragonsuite.json"

    if not config_path.exists():
        return []

    with open(config_path) as f:
        config = json.load(f)

    # Get services from config
    services = config.get("services", [])

    # Return service names and ports
    return [
        {
            "name": s.get("name"),
            "port": s.get("port"),
            "id": s.get("id"),
            "category": s.get("category")
        }
        for s in services
    ]


def create_daily_note(date_str, summary, changes, lessons, env_changes):
    """Create or update Obsidian daily note"""
    note_path = DAILY_NOTES_DIR / f"{date_str}.md"

    content = f"""# {date_str} - Claude Code Session

## Summary
{summary}

## Changes Made
{changes}

## Lessons Learned
{lessons if lessons else "*No new lessons captured*"}

## Environment Changes
{env_changes if env_changes else "*No environment changes*"}

## Git Status
```bash
{get_git_changes()['status'] or 'No uncommitted changes'}
```

## Recent Commits
```
{get_git_changes()['commits'] or 'No recent commits'}
```

---

**Tags:** #session-review #claude-code #knowledge-base
**Created:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""

    with open(note_path, 'w') as f:
        f.write(content)

    print(f"{Colors.OKGREEN}✓ Created daily note: {note_path}{Colors.ENDC}")
    return note_path


def main():
    """Main session review workflow"""
    print_header("Claude Code Session Review")

    date_str = datetime.now().strftime("%Y-%m-%d")

    # 1. Get git changes
    print_section("1. Scanning Git Changes")
    git_info = get_git_changes()

    if git_info['files_changed']:
        print(f"{Colors.OKGREEN}Found {len(git_info['files_changed'])} changed files:{Colors.ENDC}")
        for file in git_info['files_changed'][:10]:  # Show first 10
            print(f"  {file}")
        if len(git_info['files_changed']) > 10:
            print(f"  ... and {len(git_info['files_changed']) - 10} more")
    else:
        print(f"{Colors.WARNING}No uncommitted changes found{Colors.ENDC}")

    # 2. Scan for new services
    print_section("2. Scanning for New Services")
    services = scan_for_new_services()
    print(f"{Colors.OKGREEN}Found {len(services)} total services in Dragonsuite{Colors.ENDC}")

    # 3. Gather session information
    print_section("3. Session Information")
    print("\n" + Colors.BOLD + "Enter session summary (what did you work on?):" + Colors.ENDC)
    print(Colors.OKCYAN + "(Press Enter twice when done)" + Colors.ENDC)

    summary_lines = []
    while True:
        line = input()
        if line == "" and summary_lines and summary_lines[-1] == "":
            summary_lines.pop()  # Remove last empty line
            break
        summary_lines.append(line)

    summary = "\n".join(summary_lines) if summary_lines else "*No summary provided*"

    # 4. Format changes for note
    print_section("4. Generating Session Report")

    changes_text = ""
    if git_info['files_changed']:
        changes_text = "### Modified Files\n"
        for file in git_info['files_changed']:
            changes_text += f"- `{file}`\n"
    else:
        changes_text = "*No file changes detected*"

    # 5. Ask for lessons learned
    print("\n" + Colors.BOLD + "Any lessons learned? (optional, Enter to skip):" + Colors.ENDC)
    lessons_input = input().strip()
    lessons = f"- {lessons_input}" if lessons_input else ""

    # 6. Ask for environment changes
    print("\n" + Colors.BOLD + "Environment changes (new ports, services, venvs)? (optional, Enter to skip):" + Colors.ENDC)
    env_input = input().strip()
    env_changes = f"- {env_input}" if env_input else ""

    # 7. Create daily note
    print_section("5. Creating Daily Note")
    note_path = create_daily_note(date_str, summary, changes_text, lessons, env_changes)

    # 8. Summary
    print_section("Session Review Complete")
    print(f"{Colors.OKGREEN}✓ Daily note created: {note_path}{Colors.ENDC}")
    print(f"\n{Colors.BOLD}Next steps:{Colors.ENDC}")
    print(f"  1. Review the daily note in Obsidian")
    print(f"  2. Update memory files if needed (memory/common_issues.md)")
    print(f"  3. Update CLAUDE.md if services/ports changed")
    print(f"  4. Commit changes: git add . && git commit")

    print(f"\n{Colors.OKCYAN}Tip: Use '{Colors.BOLD}KB{Colors.ENDC}{Colors.OKCYAN}' as shorthand for Knowledge Base{Colors.ENDC}")
    print(f"{Colors.OKCYAN}  (CLAUDE.md + memory/ + Obsidian vault){Colors.ENDC}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.WARNING}Session review cancelled.{Colors.ENDC}")
        sys.exit(0)
    except Exception as e:
        print(f"\n{Colors.FAIL}Error: {e}{Colors.ENDC}")
        sys.exit(1)
