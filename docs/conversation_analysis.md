# Claude Code Conversation Analysis

Automated tools for reviewing and learning from past Claude Code conversations.

## Overview

Claude Code stores conversation metadata in `~/.claude/history.jsonl`. These scripts help you:

1. **Export** conversation history to reviewable markdown files
2. **Analyze** conversations using Claude API to extract lessons learned
3. **Synthesize** insights into actionable documentation

## Quick Start

### 1. Export Conversations

```bash
# List all conversation sessions
python3 scripts/export_conversations.py --list

# Export to markdown files
python3 scripts/export_conversations.py --export ~/claude_conversations

# List only recent 20 sessions
python3 scripts/export_conversations.py --list --limit 20
```

**Output:**
- `~/claude_conversations/INDEX.md` - Chronological index
- `~/claude_conversations/session_<id>.md` - Individual session files

### 2. Analyze for Lessons Learned

**Prerequisites:**
- `ANTHROPIC_API_KEY` in `/srv/containers/edq/.env`
- `pip install anthropic` in your Python environment

```bash
# Analyze exported conversations
python3 scripts/analyze_conversations.py ~/claude_conversations

# Limit to 20 most substantial conversations
python3 scripts/analyze_conversations.py ~/claude_conversations --limit 20

# Save individual analyses too
python3 scripts/analyze_conversations.py ~/claude_conversations --individual

# Custom output location
python3 scripts/analyze_conversations.py ~/claude_conversations \
  --output /srv/containers/edq/docs/LESSONS_LEARNED.md
```

**Output:**
- `~/claude_conversations/LESSONS_LEARNED.md` - Comprehensive synthesis
- `~/claude_conversations/analysis_<session_id>.md` - Individual analyses (if --individual)

### 3. Complete Workflow

```bash
# Export all conversations
python3 scripts/export_conversations.py \
  --export ~/claude_conversations

# Analyze the 30 most substantial sessions
python3 scripts/analyze_conversations.py \
  ~/claude_conversations \
  --limit 30 \
  --output /srv/containers/edq/docs/LESSONS_LEARNED.md

# Review the output
cat /srv/containers/edq/docs/LESSONS_LEARNED.md

# Integrate findings into CLAUDE.md and MEMORY.md as needed
```

## What Gets Analyzed

The analysis extracts:

### 1. Configuration Insights
- Environment variables and setup
- Tool configurations
- Port assignments
- Dependency management

### 2. Common Issues & Solutions
- Problems encountered
- Error resolutions
- Workarounds
- Debugging patterns

### 3. Best Practices
- Successful workflows
- Effective tool usage
- Architecture decisions
- Performance optimizations

### 4. Mistakes to Avoid
- Anti-patterns
- Failed approaches
- Lessons from errors

### 5. Tool Usage Patterns
- When to use specific tools
- Tool combinations
- Efficient workflows

## Cost Considerations

The `analyze_conversations.py` script uses Claude Sonnet 4.5 via API:

- **Per conversation:** ~50K input tokens + 4K output tokens
- **Synthesis:** ~100K input tokens + 16K output tokens
- **30 conversations:** ~$5-10 USD (as of 2026-02)

**Tips to reduce cost:**
- Use `--limit` to analyze fewer conversations
- Start with 10-15 sessions to test
- Focus on recent/substantial conversations

## Output Format

### INDEX.md
```markdown
# Claude Code Conversation History

**Generated:** 2026-02-08 10:30:00
**Total Sessions:** 50

---

## [2026-01-20 14:30] Installed Wan2GP video generation...

- **Session ID:** `abc123...`
- **Project:** `/home/edq`
- **Messages:** 15
- **File:** [session_abc123.md](session_abc123.md)

---
```

### LESSONS_LEARNED.md
```markdown
# Lessons Learned from Claude Code Sessions

**Generated:** 2026-02-08 10:35:00
**Analyzed:** 30 conversations

---

## Environment & Configuration

### Lesson 1: CUDA Version Compatibility

**What:** RTX 5070 Ti (Blackwell) requires PyTorch with CUDA 12.8+
**Why:** ...
**How:** ...

[More sections...]
```

## Integration with Memory Systems

After generating `LESSONS_LEARNED.md`:

1. **Review** the output for accuracy and relevance
2. **Merge** key lessons into `/srv/containers/edq/CLAUDE.md`
3. **Update** `~/.claude/projects/-srv-containers-edq/memory/MEMORY.md`
4. **Create** topic-specific files if needed (e.g., `debugging.md`)

## Manual Conversation Review

To manually review a specific conversation:

```bash
# Get session ID from INDEX.md or export output
SESSION_ID="abc123-def456-..."

# Resume that conversation in read-only mode
claude --resume $SESSION_ID
```

## Troubleshooting

### "No conversation files found"
- Run `export_conversations.py` first
- Check that `~/.claude/history.jsonl` exists

### "ANTHROPIC_API_KEY not found"
- Ensure `/srv/containers/edq/.env` contains `ANTHROPIC_API_KEY=sk-ant-...`
- Source the .env file: `source /srv/containers/edq/.env`

### "Analysis failed"
- Check API key is valid and has credits
- Reduce `--limit` if conversations are too large
- Check individual error messages in output

## Advanced Usage

### Export Only Recent Sessions

```bash
# Export only sessions from last 30 days
# (Would need to modify script to add date filtering)
```

### Analyze Specific Project

```bash
# Filter by project directory
grep "/srv/containers/edq" ~/.claude/history.jsonl | \
  python3 scripts/export_conversations.py --export ~/claude_conversations_edq
```

### Create Obsidian Vault

```bash
# Export to Obsidian vault
python3 scripts/export_conversations.py \
  --export ~/Documents/Obsidian/Claude\ Conversations

# Now browsable in Obsidian with backlinks and graph view
```

## See Also

- `/srv/containers/edq/CLAUDE.md` - Project instructions
- `~/.claude/projects/-srv-containers-edq/memory/MEMORY.md` - Auto memory
- Claude Code documentation: https://github.com/anthropics/claude-code
