#!/bin/bash
# Batch analyze Claude Code conversation history
# Automatically resumes each session and extracts lessons learned

set -e

# Configuration
OUTPUT_DIR="${1:-$HOME/claude_conversations}"
ANALYSIS_PROMPT="${2:-Analyze this conversation and extract any lessons learned, best practices, configuration insights, or mistakes to avoid. Focus on actionable insights that would be valuable to document in CLAUDE.md or MEMORY.md. Be specific about commands, file paths, settings, etc. Format as markdown.}"

mkdir -p "$OUTPUT_DIR/analyses"
mkdir -p "$OUTPUT_DIR/sessions"

echo "🔍 Batch Conversation Analysis"
echo "================================"
echo ""
echo "Output directory: $OUTPUT_DIR"
echo ""

# Extract unique session IDs from history.jsonl
echo "📚 Extracting session IDs..."
SESSION_IDS=$(jq -r 'select(.sessionId) | .sessionId' ~/.claude/history.jsonl | sort -u)

# Count sessions
TOTAL=$(echo "$SESSION_IDS" | wc -l)
echo "   Found $TOTAL unique sessions"
echo ""

# Create temporary prompt file
PROMPT_FILE=$(mktemp)
echo "$ANALYSIS_PROMPT" > "$PROMPT_FILE"

# Process each session
CURRENT=0
SUCCESSFUL=0
FAILED=0

while IFS= read -r SESSION_ID; do
    CURRENT=$((CURRENT + 1))

    # Get first message from this session for context
    FIRST_MSG=$(jq -r "select(.sessionId == \"$SESSION_ID\") | .display" ~/.claude/history.jsonl | head -1 | cut -c1-60)

    echo "[$CURRENT/$TOTAL] $SESSION_ID"
    echo "   First: $FIRST_MSG"

    # Skip if already analyzed
    ANALYSIS_FILE="$OUTPUT_DIR/analyses/${SESSION_ID}.md"
    if [ -f "$ANALYSIS_FILE" ]; then
        echo "   ⏭️  Already analyzed (skipping)"
        echo ""
        continue
    fi

    # Resume session with analysis prompt
    echo "   🔄 Resuming and analyzing..."

    # Use claude CLI to resume session and send analysis prompt
    # --print mode to get output directly
    if claude --resume "$SESSION_ID" --print < "$PROMPT_FILE" > "$ANALYSIS_FILE" 2>/dev/null; then
        SUCCESSFUL=$((SUCCESSFUL + 1))
        echo "   ✅ Analysis saved"
    else
        FAILED=$((FAILED + 1))
        echo "   ❌ Failed to analyze"
        rm -f "$ANALYSIS_FILE"
    fi

    echo ""

    # Rate limiting (be nice to the API)
    sleep 2

done <<< "$SESSION_IDS"

# Cleanup
rm -f "$PROMPT_FILE"

# Summary
echo ""
echo "================================"
echo "📊 Summary"
echo "================================"
echo "Total sessions:    $TOTAL"
echo "Successfully analyzed: $SUCCESSFUL"
echo "Failed:            $FAILED"
echo ""
echo "Output directory:  $OUTPUT_DIR/analyses/"
echo ""

# Generate index
echo "📝 Generating index..."

INDEX_FILE="$OUTPUT_DIR/INDEX.md"

cat > "$INDEX_FILE" <<EOF
# Conversation Analysis Index

**Generated:** $(date '+%Y-%m-%d %H:%M:%S')
**Total Sessions:** $TOTAL
**Analyzed:** $SUCCESSFUL

---

EOF

# Add each analysis to index
for ANALYSIS_FILE in "$OUTPUT_DIR/analyses"/*.md; do
    if [ -f "$ANALYSIS_FILE" ]; then
        SESSION_ID=$(basename "$ANALYSIS_FILE" .md)

        # Get metadata from history
        FIRST_MSG=$(jq -r "select(.sessionId == \"$SESSION_ID\") | .display" ~/.claude/history.jsonl | head -1 | cut -c1-80)
        TIMESTAMP=$(jq -r "select(.sessionId == \"$SESSION_ID\") | .timestamp" ~/.claude/history.jsonl | head -1)
        DATE=$(date -d "@$((TIMESTAMP / 1000))" '+%Y-%m-%d %H:%M' 2>/dev/null || echo "Unknown")
        PROJECT=$(jq -r "select(.sessionId == \"$SESSION_ID\") | .project" ~/.claude/history.jsonl | head -1)

        cat >> "$INDEX_FILE" <<EOF
## [$DATE] $FIRST_MSG

- **Session ID:** \`$SESSION_ID\`
- **Project:** \`$PROJECT\`
- **Analysis:** [${SESSION_ID}.md](analyses/${SESSION_ID}.md)

---

EOF
    fi
done

echo "✅ Index created: $INDEX_FILE"
echo ""
echo "💡 Next steps:"
echo "   1. Review analyses in: $OUTPUT_DIR/analyses/"
echo "   2. Read index at: $INDEX_FILE"
echo "   3. Run synthesize script to combine insights"
echo ""
echo "To synthesize all analyses:"
echo "   python3 scripts/synthesize_lessons.py $OUTPUT_DIR"
echo ""
