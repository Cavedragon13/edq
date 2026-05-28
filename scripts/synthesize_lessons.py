#!/usr/bin/env python3
"""
Synthesize individual conversation analyses into comprehensive lessons learned.

Reads all .md files from the analyses directory and uses Claude API
to combine them into actionable documentation.
"""

import anthropic

sys.path.insert(0, '/srv/containers/edq')
from scripts import provider_models
import sys
import os
from pathlib import Path
from datetime import datetime

def anthropic_model(task='analysis'):
    preferred = os.environ.get('ANTHROPIC_MODEL')
    return provider_models.resolve_model('anthropic', task, preferred=preferred).get('model') or 'claude-sonnet-4-6'

def load_api_key():
    """Load Anthropic API key from .env file."""
    env_file = Path('/srv/containers/edq/.env')

    if not env_file.exists():
        print("❌ .env file not found at /srv/containers/edq/.env")
        return None

    with open(env_file) as f:
        for line in f:
            if line.startswith('ANTHROPIC_API_KEY='):
                return line.split('=', 1)[1].strip().strip('"\'')

    return None

def load_analyses(analyses_dir: Path, limit: int = 50):
    """Load all analysis markdown files."""
    analyses = []

    for analysis_file in sorted(analyses_dir.glob('*.md'))[:limit]:
        with open(analysis_file) as f:
            content = f.read()

        if content.strip() and len(content) > 100:  # Skip empty/trivial analyses
            analyses.append({
                'session_id': analysis_file.stem,
                'content': content,
                'size': len(content)
            })

    return analyses

def synthesize_with_claude(client: anthropic.Anthropic, analyses: list) -> str:
    """Use Claude to synthesize all analyses into comprehensive lessons."""

    # Sort by size and take most substantial conversations
    analyses.sort(key=lambda x: x['size'], reverse=True)
    analyses = analyses[:40]  # Top 40 most substantial

    # Combine analyses
    combined = "\n\n---\n\n".join([
        f"# Analysis {i+1}\n\n{a['content']}"
        for i, a in enumerate(analyses)
    ])

    prompt = f"""
Analyze these {len(analyses)} conversation analyses and create a comprehensive "Lessons Learned" document.

**Your task:**
1. **Identify patterns** - What issues, solutions, or insights appear repeatedly?
2. **Consolidate** - Combine similar lessons, don't repeat the same lesson 40 times
3. **Prioritize** - Put the most impactful lessons first
4. **Be actionable** - Every lesson should have clear guidance on what to do
5. **Include specifics** - Commands, file paths, configurations, code snippets
6. **Format for documentation** - Ready to add to CLAUDE.md or MEMORY.md

**Categories to cover:**
- Environment & Hardware Configuration
- Tool Usage & Workflows
- Common Issues & Solutions
- Architecture & Design Decisions
- Performance & Optimization
- Security & Best Practices
- API & Integration Patterns
- Development Workflows

**Format each lesson as:**
```markdown
### Lesson Title

**Issue/Context:** Brief description of the problem or scenario

**Solution:** What worked and why

**Implementation:**
- Specific steps, commands, or code
- Configuration examples
- File paths

**Related:** Cross-references to related lessons or docs
```

**Important:**
- Skip generic advice - focus on project-specific insights
- Don't just list what was done - explain WHY it matters
- Include anti-patterns (what NOT to do)
- Reference actual files, ports, tools from this project

---

{combined[:300000]}  # Limit to 300K chars
"""

    try:
        print("   Sending to Claude API...")
        message = client.messages.create(
            model=anthropic_model(),
            max_tokens=16000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        return message.content[0].text

    except Exception as e:
        return f"❌ Error: {e}"

def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python3 synthesize_lessons.py <conversations_dir>")
        print("Example: python3 synthesize_lessons.py ~/claude_conversations")
        sys.exit(1)

    conversations_dir = Path(sys.argv[1]).expanduser()
    analyses_dir = conversations_dir / "analyses"

    if not analyses_dir.exists():
        print(f"❌ Analyses directory not found: {analyses_dir}")
        print("   Run batch_analyze_history.sh first")
        sys.exit(1)

    # Load API key
    print("🔑 Loading API key...")
    api_key = load_api_key()

    if not api_key:
        print("❌ ANTHROPIC_API_KEY not found in /srv/containers/edq/.env")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    # Load analyses
    print(f"📚 Loading analyses from {analyses_dir}...")
    analyses = load_analyses(analyses_dir)

    if not analyses:
        print(f"❌ No analysis files found in {analyses_dir}")
        sys.exit(1)

    print(f"   Found {len(analyses)} analyses")

    # Synthesize
    print(f"\n🧠 Synthesizing lessons learned...")
    lessons = synthesize_with_claude(client, analyses)

    # Save output
    output_file = conversations_dir / "LESSONS_LEARNED.md"

    with open(output_file, 'w') as f:
        f.write(f"# Lessons Learned from {len(analyses)} Claude Code Sessions\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Analyzed Conversations:** {len(analyses)}\n\n")
        f.write("---\n\n")
        f.write(lessons)

    print(f"\n✅ Synthesis complete!")
    print(f"📄 Output: {output_file}")
    print(f"\n💡 Next steps:")
    print(f"   1. Review: {output_file}")
    print(f"   2. Merge relevant sections into /srv/containers/edq/CLAUDE.md")
    print(f"   3. Update ~/.claude/projects/-srv-containers-edq/memory/MEMORY.md")

if __name__ == '__main__':
    main()
