# Automated Conversation Review Guide

**Problem:** You have 50+ previous Claude Code conversations and want to extract lessons learned without manually reviewing each one.

**Solution:** Automated scripts that do the tedious work for you.

## Quick Start (Recommended)

### Option 1: Fully Automated (Uses Claude API)

```bash
# Step 1: Batch analyze all 47 conversations
# This automatically resumes each conversation and extracts lessons
bash scripts/batch_analyze_history.sh ~/claude_conversations

# Wait for it to complete (~2-5 minutes with rate limiting)
# This will create ~/claude_conversations/analyses/*.md

# Step 2: Synthesize all analyses into one comprehensive document
python3 scripts/synthesize_lessons.py ~/claude_conversations

# Output: ~/claude_conversations/LESSONS_LEARNED.md
```

**Cost:** ~$5-10 USD (Claude API charges)
**Time:** ~5-10 minutes total
**Effort:** Zero - fully automated

### Option 2: Manual Export (Free)

```bash
# Export conversation metadata to markdown
python3 scripts/export_conversations.py --export ~/claude_conversations

# Review the INDEX.md and individual session files
cat ~/claude_conversations/INDEX.md

# Manually review interesting sessions
```

**Cost:** Free
**Time:** ~30 seconds to export, then manual review
**Effort:** Medium - you review manually

## What You Get

### From batch_analyze_history.sh

Individual analysis files for each conversation in `~/claude_conversations/analyses/`:

- `abc123-def456.md` - Lessons from one conversation
- `xyz789-abc123.md` - Lessons from another conversation
- ... (one per conversation)

Each analysis contains:

- Configuration insights
- Problems solved
- Best practices discovered
- Mistakes to avoid
- Relevant commands/code

### From synthesize_lessons.py

One comprehensive file: `~/claude_conversations/LESSONS_LEARNED.md`

Contains:

- **Consolidated lessons** - Common patterns across all conversations
- **Prioritized** - Most important lessons first
- **Actionable** - Clear guidance on what to do
- **Specific** - Commands, paths, configurations
- **Categorized** - Grouped by topic (Environment, Tools, Performance, etc.)

## Detailed Usage

### List Your Conversations

```bash
# See all 47 conversations
python3 scripts/export_conversations.py --list

# Just the 10 most recent
python3 scripts/export_conversations.py --list --limit 10
```

### Export to Markdown (No API needed)

```bash
# Export all conversations to markdown files
python3 scripts/export_conversations.py --export ~/claude_conversations

# This creates:
# - INDEX.md (overview)
# - session_<id>.md (one per conversation with user messages)
```

### Batch Analyze with Custom Prompt

```bash
# Use a custom analysis prompt
bash scripts/batch_analyze_history.sh \
  ~/claude_conversations \
  "Extract all Python package versions, port numbers, and configuration files mentioned. List them in a table."
```

### Analyze Only Specific Conversations

```bash
# Edit the script to filter by date, project, or message content
# Or manually run analysis on specific sessions

# Example: analyze just one session
SESSION_ID="cfed7c6b-76aa-4c23-af9e-9488a10889ca"
echo "Analyze this conversation for lessons learned." | \
  claude --resume "$SESSION_ID" --print > ~/claude_conversations/analyses/${SESSION_ID}.md
```

### Integration with Obsidian

```bash
# Export directly to Obsidian vault
python3 scripts/export_conversations.py \
  --export ~/Documents/Obsidian/Claude\ Conversations

# Now you can browse in Obsidian with:
# - Backlinks
# - Graph view
# - Search across all conversations
# - Link to other notes
```

## How It Works

### 1. batch_analyze_history.sh

```
For each session ID in ~/.claude/history.jsonl:
  1. Resume that conversation: claude --resume <session-id>
  2. Send analysis prompt
  3. Save Claude's analysis to analyses/<session-id>.md
  4. Rate limit (2 second delay between sessions)
```

### 2. synthesize_lessons.py

```
1. Load all individual analyses
2. Sort by size (most substantial first)
3. Combine top 40 analyses
4. Send to Claude API: "Find patterns, consolidate, prioritize"
5. Save comprehensive document
```

## Real-World Example

Here's what you might discover:

````markdown
### Memory Optimization for 16GB VRAM

**Issue:** Large diffusion models OOM on RTX 5070 Ti (16GB VRAM)

**Solution:** Use `enable_sequential_cpu_offload()` + environment variable

**Implementation:**

```python
# In launcher script BEFORE python command:
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

# In Python script:
pipeline.enable_sequential_cpu_offload()
if hasattr(pipeline, 'vae'):
    pipeline.vae.enable_slicing()
    pipeline.vae.enable_tiling()
```
````

**Applied in:**

- Z-Image Base (port 8011)
- Qwen-Image-Layered (port 8013)
- HeartMuLa (port 8004)

**Related:** See CLAUDE.md section "Memory Optimization for Large Models"

````

This specific lesson was discovered across 3-4 different conversations where you solved the same problem!

## Tips

### Reduce API Costs

```bash
# Analyze only 20 most recent conversations
# Modify batch_analyze_history.sh line 35:
SESSION_IDS=$(jq -r 'select(.sessionId) | .sessionId' ~/.claude/history.jsonl | sort -u | tail -20)

# Or analyze only conversations with many messages (more substantial)
# This requires modifying the script to count messages per session
````

### Resume Analysis After Failure

```bash
# The script skips already-analyzed sessions
# So if it fails halfway, just re-run:
bash scripts/batch_analyze_history.sh ~/claude_conversations

# It will say "⏭️ Already analyzed (skipping)" for completed ones
```

### Export for Sharing

```bash
# Create a shareable archive
tar -czf claude_conversations_$(date +%Y%m%d).tar.gz ~/claude_conversations/

# Send to another machine or backup
```

## Troubleshooting

### "ANTHROPIC_API_KEY not found"

```bash
# Check .env file
cat /srv/containers/edq/.env | grep ANTHROPIC

# If missing, add it:
echo 'ANTHROPIC_API_KEY=sk-ant-api03-...' >> /srv/containers/edq/.env
```

### "No conversation files found"

```bash
# Run export first
python3 scripts/export_conversations.py --export ~/claude_conversations

# Then try analysis again
python3 scripts/synthesize_lessons.py ~/claude_conversations
```

### Rate Limiting / API Errors

```bash
# Increase sleep time in batch_analyze_history.sh
# Line 87: sleep 2  →  sleep 5
```

### Script Permission Denied

```bash
chmod +x scripts/batch_analyze_history.sh
chmod +x scripts/export_conversations.py
chmod +x scripts/synthesize_lessons.py
```

## Next Steps After Analysis

1. **Review** `~/claude_conversations/LESSONS_LEARNED.md`

2. **Merge** relevant lessons into project documentation:

   ```bash
   # Add to CLAUDE.md
   cat ~/claude_conversations/LESSONS_LEARNED.md >> /srv/containers/edq/CLAUDE.md

   # Or selectively copy sections
   ```

3. **Update** auto memory:

   ```bash
   # Add key insights to MEMORY.md
   nano ~/.claude/projects/-srv-containers-edq/memory/MEMORY.md
   ```

4. **Create** topic files for detailed notes:
   ```bash
   mkdir -p ~/.claude/projects/-srv-containers-edq/memory/
   # Create debugging.md, patterns.md, etc.
   ```

## See Also

- [Full Documentation](conversation_analysis.md) - Detailed technical docs
- [CLAUDE.md](/srv/containers/edq/CLAUDE.md) - Project instructions
- [MEMORY.md](~/.claude/projects/-srv-containers-edq/memory/MEMORY.md) - Auto memory
