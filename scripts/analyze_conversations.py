#!/usr/bin/env python3
"""
Analyze Claude Code conversation history and extract lessons learned.

This script uses the Anthropic API to analyze conversations and extract:
- Common patterns and issues
- Best practices discovered
- Mistakes to avoid
- Configuration insights
- Tool usage patterns
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict
import anthropic

def load_api_key():
    """Load Anthropic API key from .env file."""
    env_file = Path('/srv/containers/edq/.env')

    if not env_file.exists():
        print("❌ .env file not found")
        print("   Expected at: /srv/containers/edq/.env")
        return None

    with open(env_file) as f:
        for line in f:
            if line.startswith('ANTHROPIC_API_KEY='):
                return line.split('=', 1)[1].strip().strip('"\'')

    return None

def load_conversation_metadata(conversations_dir: Path) -> List[Dict]:
    """Load conversation metadata from exported markdown files."""
    conversations = []

    for session_file in conversations_dir.glob('session_*.md'):
        with open(session_file) as f:
            content = f.read()

        # Extract metadata
        lines = content.split('\n')
        session_id = session_file.stem.replace('session_', '')

        conversations.append({
            'id': session_id,
            'file': session_file,
            'content': content,
            'size': len(content)
        })

    return conversations

def analyze_conversation(client: anthropic.Anthropic, conversation: Dict) -> Dict:
    """Analyze a single conversation for lessons learned."""

    analysis_prompt = f"""
Analyze this Claude Code conversation session and extract lessons learned.

Focus on:
1. **Configuration insights** - Settings, environment variables, tool configurations
2. **Common issues** - Problems encountered and how they were solved
3. **Best practices** - Successful patterns and approaches
4. **Mistakes to avoid** - What didn't work or caused problems
5. **Tool usage patterns** - How different tools were effectively used
6. **Architecture decisions** - Design choices and their rationale

Be specific and actionable. Include:
- Code snippets or commands where relevant
- File paths and configurations
- Port numbers, dependencies, etc.
- "Why" explanations, not just "what"

Format your response as markdown with clear sections.

---

{conversation['content'][:50000]}  # Limit to first 50K chars
"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=4096,
            messages=[
                {"role": "user", "content": analysis_prompt}
            ]
        )

        return {
            'session_id': conversation['id'],
            'analysis': message.content[0].text,
            'success': True
        }

    except Exception as e:
        return {
            'session_id': conversation['id'],
            'error': str(e),
            'success': False
        }

def synthesize_lessons(client: anthropic.Anthropic, analyses: List[str]) -> str:
    """Synthesize all individual analyses into comprehensive lessons."""

    combined_analyses = "\n\n---\n\n".join(analyses[:30])  # First 30 sessions

    synthesis_prompt = f"""
You are analyzing 30+ Claude Code conversation sessions to extract universal lessons learned.

Review the individual session analyses below and create a comprehensive "Lessons Learned" document.

**Requirements:**

1. **Consolidate common patterns** - If the same lesson appears in multiple sessions, combine them
2. **Prioritize by impact** - Put the most important lessons first
3. **Be actionable** - Each lesson should have clear "what to do" guidance
4. **Include examples** - Code snippets, commands, configurations
5. **Categorize** - Group related lessons together
6. **Format for CLAUDE.md** - Output should be ready to append to project documentation

**Categories to cover:**
- Environment & Configuration
- Tool Usage Patterns
- Common Pitfalls & Solutions
- Architecture Decisions
- Performance Optimizations
- Security & Best Practices
- Workflow Improvements

**Format:**
Use markdown with clear headings. Each lesson should have:
- Title (what)
- Explanation (why)
- Example or implementation (how)

---

{combined_analyses}
"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=16000,
            messages=[
                {"role": "user", "content": synthesis_prompt}
            ]
        )

        return message.content[0].text

    except Exception as e:
        return f"❌ Error synthesizing lessons: {e}"

def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Analyze Claude Code conversations for lessons learned'
    )
    parser.add_argument(
        'conversations_dir',
        type=Path,
        help='Directory containing exported conversation markdown files'
    )
    parser.add_argument(
        '--output', '-o',
        type=Path,
        default=Path('~/claude_conversations/LESSONS_LEARNED.md').expanduser(),
        help='Output file for lessons learned (default: ~/claude_conversations/LESSONS_LEARNED.md)'
    )
    parser.add_argument(
        '--limit', '-l',
        type=int,
        default=30,
        help='Number of conversations to analyze (default: 30)'
    )
    parser.add_argument(
        '--individual',
        action='store_true',
        help='Save individual analysis for each conversation'
    )

    args = parser.parse_args()

    # Load API key
    print("🔑 Loading API key...")
    api_key = load_api_key()

    if not api_key:
        print("❌ ANTHROPIC_API_KEY not found in /srv/containers/edq/.env")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    # Load conversations
    print(f"📚 Loading conversations from {args.conversations_dir}...")
    conversations = load_conversation_metadata(args.conversations_dir)

    if not conversations:
        print(f"❌ No conversation files found in {args.conversations_dir}")
        print("   Run export_conversations.py first to export conversations")
        sys.exit(1)

    print(f"   Found {len(conversations)} conversations")

    # Sort by size (larger = more substantial conversations)
    conversations.sort(key=lambda x: x['size'], reverse=True)
    conversations = conversations[:args.limit]

    # Analyze each conversation
    print(f"\n🔍 Analyzing {len(conversations)} conversations...")
    analyses = []

    for i, conv in enumerate(conversations, 1):
        print(f"   [{i}/{len(conversations)}] Analyzing {conv['id'][:8]}...")

        result = analyze_conversation(client, conv)

        if result['success']:
            analyses.append(result['analysis'])

            if args.individual:
                individual_file = args.conversations_dir / f"analysis_{result['session_id']}.md"
                with open(individual_file, 'w') as f:
                    f.write(result['analysis'])
        else:
            print(f"      ⚠️  Error: {result.get('error', 'Unknown')}")

    if not analyses:
        print("❌ No successful analyses")
        sys.exit(1)

    # Synthesize into comprehensive lessons
    print(f"\n🧠 Synthesizing lessons from {len(analyses)} analyses...")
    lessons = synthesize_lessons(client, analyses)

    # Save output
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with open(args.output, 'w') as f:
        f.write(f"# Lessons Learned from Claude Code Sessions\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Analyzed:** {len(analyses)} conversations\n\n")
        f.write("---\n\n")
        f.write(lessons)

    print(f"\n✅ Analysis complete!")
    print(f"📄 Output: {args.output}")
    print(f"\n💡 Next steps:")
    print(f"   1. Review {args.output}")
    print(f"   2. Add relevant sections to /srv/containers/edq/CLAUDE.md")
    print(f"   3. Update ~/.claude/projects/-srv-containers-edq/memory/MEMORY.md")

if __name__ == '__main__':
    main()
