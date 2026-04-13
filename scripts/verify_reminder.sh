#!/bin/bash
# verify_reminder.sh — Stop hook: enforces the full ship gate before "done"
# Fires when completion language is detected OR when code/services were written.
# Outputs both a systemMessage (user sees it) and additionalContext (injected into model).

STDIN=$(cat)
SESSION_ID=$(echo "$STDIN" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('session_id',''))" 2>/dev/null)

if [ -z "$SESSION_ID" ]; then
  exit 0
fi

# Find transcript file — try all known project dirs
TRANSCRIPT=""
for DIR in \
  "$HOME/.claude/projects/-srv-containers-edq-projects" \
  "$HOME/.claude/projects/-srv-containers-edq" \
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

# Analyse transcript: check for completion language AND whether code was written
python3 - "$TRANSCRIPT" << 'PYEOF'
import sys, json

path = sys.argv[1]
last_text = ""
code_written = False
in_last_turn = False  # True once we hit the last user message
COMPLETION_KEYWORDS = [
    "ready", "done", "complete", "should work", "all set", "finished",
    "working now", "up and running", "good to go", "successfully",
    "is live", "is running", "was added", "has been", "rebuilt", "restarted"
]
CODE_EXTENSIONS = ('.py', '.ts', '.tsx', '.js', '.jsx', '.sh', '.html', '.css', '.json')

# Load all lines, then walk backwards to find the last user message boundary
lines = []
with open(path) as f:
    for line in f:
        try:
            lines.append(json.loads(line))
        except Exception:
            continue

# Find index of the last user message
last_user_idx = -1
for i in range(len(lines) - 1, -1, -1):
    if lines[i].get("type") == "user":
        last_user_idx = i
        break

# Extract last assistant text (anywhere in session — completion language check)
for obj in lines:
    if obj.get("type") == "assistant":
        content = obj.get("message", {}).get("content", [])
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                last_text = block["text"]
            elif isinstance(block, str):
                last_text = block

# Check code_written only in the last assistant turn (after last user message)
for obj in lines[last_user_idx + 1:]:
    if obj.get("type") == "assistant":
        msg_content = obj.get("message", {}).get("content", [])
        if isinstance(msg_content, list):
            for block in msg_content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    tool = block.get("name", "")
                    if tool in ("Write", "Edit"):
                        fp = block.get("input", {}).get("file_path", "")
                        if any(fp.endswith(ext) for ext in CODE_EXTENSIONS):
                            code_written = True

last_lower = last_text.lower()[:1500]
has_completion = any(kw in last_lower for kw in COMPLETION_KEYWORDS)

# Require BOTH: code was written this turn AND completion language detected
if not (has_completion and code_written):
    sys.exit(0)

GATE = (
    "SHIP GATE — not done until all of these pass:\n"
    "1. RTFM PASS: every model ID, method name, config key, response path, and URL "
    "in new/changed code is a placeholder until verified against official docs "
    "(start with docs, confirm with Reddit/SO if ambiguous). Wrong names fail "
    "completely. Check google-api.md for Gemini IDs.\n"
    "2. STACK UPDATE: port table in CLAUDE.md, dragonsuite.json, dashboard, "
    "docs/services/, venvs.md — all updated to match what was actually built.\n"
    "3. MODEL DOWNLOADS: if the service needs models on first run, download them "
    "now. User must not wait when they want to use the tool.\n"
    "4. LAUNCH + TEST: start the service, open it in a browser (Playwright or "
    "native), exercise the primary workflow end-to-end, get real output — "
    "not 'it starts', not 'the UI loads'. Actual output the user would get.\n"
    "5. REPORT: state what output was produced as evidence. Only then say Ready."
)

output = {
    "decision": "block",
    "reason": GATE,
    "systemMessage": "⛔ SHIP GATE active — see checklist in context."
}
print(json.dumps(output))
PYEOF
