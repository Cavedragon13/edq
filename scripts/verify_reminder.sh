#!/bin/bash
# verify_reminder.sh — Stop hook: checks last assistant response for completion
# language, outputs a systemMessage reminder if found.

STDIN=$(cat)
SESSION_ID=$(echo "$STDIN" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('session_id',''))" 2>/dev/null)

if [ -z "$SESSION_ID" ]; then
  exit 0
fi

# Find transcript file — try both known locations
TRANSCRIPT=""
for DIR in \
  "$HOME/.claude/projects/-srv-containers-edq-projects" \
  "$HOME/.claude/projects/-home-edq" \
  "$HOME/.claude/projects/-home-edq-ai_generated-dragonsight" \
  "$HOME/.claude/projects/-home-edq-ai_generated-dragonart-studio"; do
  if [ -f "$DIR/${SESSION_ID}.jsonl" ]; then
    TRANSCRIPT="$DIR/${SESSION_ID}.jsonl"
    break
  fi
done

if [ -z "$TRANSCRIPT" ]; then
  exit 0
fi

# Extract last assistant text block
LAST_TEXT=$(python3 - "$TRANSCRIPT" << 'PYEOF'
import sys, json

path = sys.argv[1]
last_text = ""
with open(path) as f:
    for line in f:
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if obj.get("type") == "assistant":
            content = obj.get("message", {}).get("content", [])
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    last_text = block["text"]
                elif isinstance(block, str):
                    last_text = block

print(last_text.lower()[:1000])
PYEOF
)

# Check for completion language
KEYWORDS="ready\|done\|complete\|should work\|all set\|finished\|working now\|up and running\|good to go\|successfully\|is live\|is running\|was added\|has been"

if echo "$LAST_TEXT" | grep -qi "$KEYWORDS"; then
  python3 -c "import json; print(json.dumps({'systemMessage': '🔍 verify-before-done: Confirm output actually exists at stated paths before this is done.'}))"
fi
