# Translation QA Pipeline

Automated translation system with built-in quality assessment for vocab micro-contexts.

## Quick Start

### Single Word Translation

```bash
cd /srv/containers/edq

# Translate to Spanish only
python3 scripts/vocab_translate_qa.py \
  --text "you don't really want to" \
  --word-id "reluctant" \
  --langs "es"

# Translate to all supported languages
python3 scripts/vocab_translate_qa.py \
  --text "you don't really want to" \
  --word-id "reluctant" \
  --langs "es,vi,id"
```

### Batch Processing

```bash
# Process multiple words at once
python3 scripts/vocab_translate_qa.py \
  --batch data/vocab_sample_batch.json \
  --langs "es,vi,id" \
  --retry-rejected
```

### Check Results

```bash
# Quick status summary
bash scripts/vocab_check_results.sh

# List approved translations
bash scripts/vocab_check_results.sh --approved

# List translations needing review
bash scripts/vocab_check_results.sh --review
```

## Pipeline Stages

1. **Translation A** (Qwen model) - First translation attempt
2. **Translation B** (LLaMA model) - Second translation attempt
3. **Back-translation A** - Translate A back to English
4. **Back-translation B** - Translate B back to English
5. **Critic Evaluation** (DeepSeek) - QA assessment and routing

## Output Folders

| Folder | Description |
|--------|-------------|
| `approved/` | High-confidence translations (≥85%), ready to use |
| `needs_review/` | Medium confidence (70-84%), human review recommended |
| `rejected/` | Low confidence (<70%), needs retry or manual translation |
| `qc/` | Full QC reports with all translation attempts |
| `draft_A/` | Raw Translator A outputs |
| `draft_B/` | Raw Translator B outputs |

## Routing Logic

**Approved** (auto-publish safe)
- Confidence ≥ 85%
- Meaning preserved
- Neutral tone
- No risk terms
- Placeholders intact

**Needs Review** (human check recommended)
- Confidence 70-84%
- Minor tone concerns
- A/B disagreement
- Unusual phrasing

**Rejected** (automatic retry once, then quarantine)
- Confidence < 70%
- Meaning drift
- Inappropriate tone
- Placeholder corruption

## Supported Languages

- `es` - Spanish
- `vi` - Vietnamese
- `id` - Indonesian

## Example Output

### Approved Translation (`approved/reluctant_es.json`)
```json
{
  "word_id": "reluctant",
  "target_lang": "es",
  "translation": "no quieres realmente",
  "source_en": "you don't really want to",
  "confidence": 90,
  "timestamp": "2026-02-03T22:34:34.594996"
}
```

### QC Report (`qc/reluctant_es_20260203_223434.json`)
```json
{
  "word_id": "reluctant",
  "target_lang": "es",
  "original_en": "you don't really want to",
  "translation_a": "no quieres de verdad",
  "translation_b": "no realmente quieres",
  "backtrans_a": "I don't really want it.",
  "backtrans_b": "Don't really want",
  "evaluation": {
    "decision": "needs_review",
    "confidence": 75,
    "selected": "B",
    "reason": "Translator A changes subject, B preserves meaning",
    "risks": "Minor subject shift in A"
  }
}
```

## Tips

- **Single words first**: Test new micro-contexts individually before batching
- **Check confidence**: Anything <85% should be human-reviewed
- **Use retry flag**: `--retry-rejected` automatically retries failed translations
- **Monitor QC folder**: Contains full diagnostic info for debugging

## Models Used

- **Translator A**: `qwen3:8b` (Qwen family)
- **Translator B**: `llama3.2:latest` (LLaMA family)
- **Critic**: `deepseek-r1:14b` (QA evaluation)

All models run locally via Ollama (port 11434).
