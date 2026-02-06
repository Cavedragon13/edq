# Vocab Word Database

JSON-based storage system for vocab words with automatic week/day sequencing.

## Quick Reference

### Add a Word (Auto-Sequencing)
```bash
# Automatically assigns next position (Mon → Tue → Wed → Thu → Fri → next week Mon)
python3 scripts/vocab_manage.py add "reluctant" "you don't really want to"
```

### Add a Word (Manual Position)
```bash
# Assign to specific week and day
python3 scripts/vocab_manage.py add "tenacious" "refuses to give up" --week 2 --day Mon
```

### List Words
```bash
# All words
python3 scripts/vocab_manage.py list

# Specific week
python3 scripts/vocab_manage.py list --week 1

# Specific day
python3 scripts/vocab_manage.py list --day Fri

# Week + Day combo
python3 scripts/vocab_manage.py list --week 1 --day Mon
```

### Show Word Details
```bash
python3 scripts/vocab_manage.py show reluctant
```

### Export for Translation
```bash
# Export entire week for batch translation
python3 scripts/vocab_manage.py export --week 1

# This creates: data/week_01_batch.json
# Ready to feed into: vocab_translate_qa.py --batch
```

### Database Statistics
```bash
python3 scripts/vocab_manage.py stats
```

### Delete a Word
```bash
python3 scripts/vocab_manage.py delete reluctant
```

---

## Database Structure

**Location**: `/srv/containers/edq/data/vocab_database.json`

### Metadata Section
```json
{
  "metadata": {
    "created": "2026-02-03T22:00:00.000000",
    "last_modified": "2026-02-03T23:00:00.000000",
    "total_words": 5,
    "current_week": 1,
    "current_day": "Fri"
  }
}
```

### Word Entry Format
```json
{
  "id": "reluctant",
  "word": "reluctant",
  "spelling": "R-E-L-U-C-T-A-N-T",
  "micro_context_en": "you don't really want to",
  "week": 1,
  "day": "Mon",
  "added": "2026-02-03T22:34:34.594996",
  "translations": {
    "es": null,
    "vi": null,
    "id": null
  },
  "translation_status": "pending"
}
```

---

## Sequencing Rules

1. **Week numbering**: Starts at 1, increments indefinitely
2. **Day sequence**: Mon → Tue → Wed → Thu → Fri (no weekends)
3. **Auto-advance**: Adding a new word automatically goes to next slot
4. **Manual override**: Use `--week` and `--day` to assign specific positions

---

## Translation Status Values

| Status | Meaning |
|--------|---------|
| `pending` | Not yet translated (default) |
| `translated` | Translations generated, not yet approved |
| `approved` | Translations approved, ready for rendering |

---

## Workflow: Add → Translate → Render

### Step 1: Add Words for the Week
```bash
python3 scripts/vocab_manage.py add "reluctant" "you don't really want to"
python3 scripts/vocab_manage.py add "mundane" "boring, everyday stuff"
python3 scripts/vocab_manage.py add "ambiguous" "unclear, could mean different things"
python3 scripts/vocab_manage.py add "meticulous" "very careful about small details"
python3 scripts/vocab_manage.py add "ephemeral" "lasting for a very short time"
```

### Step 2: Export Week for Translation
```bash
python3 scripts/vocab_manage.py export --week 1
```

### Step 3: Run Translation Pipeline
```bash
python3 scripts/vocab_translate_qa.py \
  --batch data/week_01_batch.json \
  --langs es,vi,id \
  --retry-rejected
```

### Step 4: Check Translation Results
```bash
bash scripts/vocab_check_results.sh
```

### Step 5: (Future) Render Videos
```bash
# Coming soon: batch render script
python3 scripts/vocab_render_batch.py --week 1
```

---

## Examples

### Planning Week 1 Content
```bash
# Monday: easier word
python3 scripts/vocab_manage.py add "happy" "feeling good"

# Tuesday-Thursday: medium difficulty
python3 scripts/vocab_manage.py add "reluctant" "you don't really want to"
python3 scripts/vocab_manage.py add "ambiguous" "unclear meaning"
python3 scripts/vocab_manage.py add "meticulous" "careful with details"

# Friday: interesting payoff word
python3 scripts/vocab_manage.py add "serendipity" "lucky accident"

# Check the week
python3 scripts/vocab_manage.py list --week 1
```

### Exporting Pending Words
```bash
# Export all words that haven't been translated yet
python3 scripts/vocab_manage.py export-batch data/pending_words.json --status pending
```

---

## Database File Location

```
/srv/containers/edq/data/
├── vocab_database.json          # Main database
├── week_01_batch.json           # Exported batch (Week 1)
├── week_02_batch.json           # Exported batch (Week 2)
└── pending_words.json           # Custom export
```

---

## Tips

1. **Batch by week**: Add 5 words at once (full Mon-Fri set) before translating
2. **Check stats**: Use `stats` command to see current progress
3. **Review before translation**: Use `list --week N` to verify context quality
4. **Export early**: Create batch files before running translations
5. **Use show command**: Verify word details including spelling format
