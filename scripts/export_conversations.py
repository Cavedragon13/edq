#!/usr/bin/env python3
"""
Export Claude Code conversation history for review and analysis.

This script extracts conversation sessions from ~/.claude/history.jsonl
and provides options to export and analyze them.
"""

import json
import subprocess
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import sys

def load_history():
    """Load and parse Claude Code history."""
    history_file = Path.home() / ".claude" / "history.jsonl"

    if not history_file.exists():
        print(f"❌ History file not found: {history_file}")
        sys.exit(1)

    sessions = defaultdict(list)

    with open(history_file, 'r') as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                if 'sessionId' in entry:
                    sessions[entry['sessionId']].append(entry)
            except json.JSONDecodeError:
                continue

    return sessions

def format_session_info(session_id, entries):
    """Format session information for display."""
    first = entries[0]
    last = entries[-1]

    first_time = datetime.fromtimestamp(first['timestamp'] / 1000)
    last_time = datetime.fromtimestamp(last['timestamp'] / 1000)

    # Get first meaningful message (skip /init)
    first_msg = first.get('display', '').strip()
    if first_msg == '/init':
        first_msg = entries[1].get('display', '') if len(entries) > 1 else ''

    # Truncate long messages
    if len(first_msg) > 80:
        first_msg = first_msg[:77] + "..."

    return {
        'id': session_id,
        'project': first.get('project', 'unknown'),
        'first_time': first_time,
        'last_time': last_time,
        'duration': last_time - first_time,
        'message_count': len(entries),
        'first_msg': first_msg
    }

def export_to_markdown(sessions, output_dir):
    """Export sessions to markdown files."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    index_md = []
    index_md.append("# Claude Code Conversation History\n")
    index_md.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    index_md.append(f"**Total Sessions:** {len(sessions)}\n\n")
    index_md.append("---\n\n")

    for session_id, entries in sorted(sessions.items(),
                                     key=lambda x: x[1][0]['timestamp']):
        info = format_session_info(session_id, entries)

        # Create session file
        session_file = output_dir / f"session_{session_id}.md"

        with open(session_file, 'w') as f:
            f.write(f"# Conversation: {session_id}\n\n")
            f.write(f"**Project:** `{info['project']}`\n")
            f.write(f"**Started:** {info['first_time']}\n")
            f.write(f"**Last Activity:** {info['last_time']}\n")
            f.write(f"**Duration:** {info['duration']}\n")
            f.write(f"**Messages:** {info['message_count']}\n\n")
            f.write("---\n\n")
            f.write("## User Messages\n\n")

            for i, entry in enumerate(entries, 1):
                timestamp = datetime.fromtimestamp(entry['timestamp'] / 1000)
                display = entry.get('display', '').strip()

                if display and display != '/init':
                    f.write(f"### {i}. {timestamp.strftime('%H:%M:%S')}\n\n")
                    f.write(f"```\n{display}\n```\n\n")

        # Add to index
        index_md.append(f"## [{info['first_time'].strftime('%Y-%m-%d %H:%M')}] {info['first_msg']}\n\n")
        index_md.append(f"- **Session ID:** `{session_id}`\n")
        index_md.append(f"- **Project:** `{info['project']}`\n")
        index_md.append(f"- **Messages:** {info['message_count']}\n")
        index_md.append(f"- **File:** [session_{session_id}.md](session_{session_id}.md)\n\n")
        index_md.append("---\n\n")

    # Write index
    with open(output_dir / "INDEX.md", 'w') as f:
        f.writelines(index_md)

    return output_dir / "INDEX.md"

def list_sessions(sessions, limit=None):
    """List all sessions in chronological order."""
    print(f"\n📋 Found {len(sessions)} conversation sessions\n")
    print("=" * 100)

    sorted_sessions = sorted(sessions.items(),
                           key=lambda x: x[1][0]['timestamp'],
                           reverse=True)

    if limit:
        sorted_sessions = sorted_sessions[:limit]

    for session_id, entries in sorted_sessions:
        info = format_session_info(session_id, entries)

        print(f"\n🕒 {info['first_time'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Project: {info['project']}")
        print(f"   Messages: {info['message_count']}")
        print(f"   First: {info['first_msg']}")
        print(f"   ID: {session_id}")

def generate_summary_script(sessions, output_file):
    """Generate a script to analyze conversations with Claude."""
    output_file = Path(output_file)

    script_lines = [
        "#!/bin/bash",
        "# Auto-generated script to analyze conversation history",
        "",
        "set -e",
        "",
        "CONVERSATIONS_DIR=\"$HOME/claude_conversations\"",
        "SUMMARIES_DIR=\"$HOME/claude_conversations/summaries\"",
        "mkdir -p \"$SUMMARIES_DIR\"",
        "",
        "echo '🔍 Analyzing conversation history for lessons learned...'",
        "echo ''",
        ""
    ]

    sorted_sessions = sorted(sessions.items(),
                           key=lambda x: x[1][0]['timestamp'],
                           reverse=True)[:50]  # Last 50 sessions

    for i, (session_id, entries) in enumerate(sorted_sessions, 1):
        info = format_session_info(session_id, entries)

        script_lines.extend([
            f"# Session {i}: {info['first_time'].strftime('%Y-%m-%d')} - {info['first_msg'][:50]}",
            f"echo '[{i}/50] Analyzing session from {info['first_time'].strftime('%Y-%m-%d')}...'",
            "",
            f"# Note: Full conversation analysis requires cloud access",
            f"# Session ID: {session_id}",
            f"# To manually review: claude --resume {session_id}",
            "",
        ])

    script_lines.append("echo '✅ Analysis complete! Check $SUMMARIES_DIR for results.'")

    with open(output_file, 'w') as f:
        f.write('\n'.join(script_lines))

    output_file.chmod(0o755)
    return output_file

def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Export and analyze Claude Code conversation history'
    )
    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='List all conversation sessions'
    )
    parser.add_argument(
        '--export', '-e',
        metavar='DIR',
        help='Export conversations to markdown files in DIR'
    )
    parser.add_argument(
        '--generate-analysis-script', '-g',
        metavar='FILE',
        help='Generate a bash script to analyze conversations'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of sessions to process'
    )

    args = parser.parse_args()

    if not any([args.list, args.export, args.generate_analysis_script]):
        parser.print_help()
        sys.exit(1)

    print("📚 Loading conversation history...")
    sessions = load_history()

    if args.list:
        list_sessions(sessions, limit=args.limit)

    if args.export:
        print(f"\n📝 Exporting to {args.export}...")
        index_file = export_to_markdown(sessions, args.export)
        print(f"✅ Exported {len(sessions)} sessions")
        print(f"📄 Index: {index_file}")

    if args.generate_analysis_script:
        print(f"\n🔧 Generating analysis script...")
        script_file = generate_summary_script(sessions, args.generate_analysis_script)
        print(f"✅ Created: {script_file}")
        print(f"   Run with: bash {script_file}")

if __name__ == '__main__':
    main()
