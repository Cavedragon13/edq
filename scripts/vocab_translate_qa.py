#!/usr/bin/env python3
"""
Translation QA Pipeline for Vocab Project
==========================================

Automates translation, back-translation, and quality assessment for vocab micro-contexts.

Pipeline:
1. Translate EN → Target (Translator A: Qwen)
2. Translate EN → Target (Translator B: LLaMA)
3. Back-translate A → EN
4. Back-translate B → EN
5. Critic evaluates and routes to: approved / needs_review / rejected

Usage:
    python vocab_translate_qa.py --text "you don't really want to" --langs es,vi,id
    python vocab_translate_qa.py --batch words.json
"""

import json
import logging
import argparse
import requests
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime

# Configuration
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
TRANSLATOR_A = "qwen3:8b"       # Qwen family
TRANSLATOR_B = "llama3.2:latest"  # LLaMA family
CRITIC_MODEL = "deepseek-r1:14b"  # QA judge

# Folder paths
BASE_DIR = Path("/srv/containers/edq/translations")
DRAFT_A_DIR = BASE_DIR / "draft_A"
DRAFT_B_DIR = BASE_DIR / "draft_B"
BACKTRANS_DIR = BASE_DIR / "backtranslations"
QC_DIR = BASE_DIR / "qc"
APPROVED_DIR = BASE_DIR / "approved"
REVIEW_DIR = BASE_DIR / "needs_review"
REJECTED_DIR = BASE_DIR / "rejected"

# Language codes
SUPPORTED_LANGS = {
    "es": "Spanish",
    "vi": "Vietnamese",
    "id": "Indonesian"
}

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def call_ollama(model: str, prompt: str, temperature: float = 0.3) -> str:
    """Call Ollama API and return generated text."""
    payload = {
        "model": model,
        "prompt": prompt,
        "temperature": temperature,
        "stream": False
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        return result.get("response", "").strip()
    except requests.exceptions.RequestException as e:
        logger.error(f"Ollama API error: {e}")
        return ""


def translate_forward(text: str, target_lang: str, model: str) -> str:
    """Translate English text to target language."""
    lang_name = SUPPORTED_LANGS.get(target_lang, target_lang)

    prompt = f"""Translate the following English phrase to {lang_name}.

Requirements:
- Keep the tone neutral and educational
- Preserve any placeholders like {{WORD}} exactly as-is
- Return ONLY the translated text, no explanations

English: {text}
{lang_name}:"""

    return call_ollama(model, prompt)


def translate_backward(text: str, source_lang: str, model: str) -> str:
    """Back-translate from target language to English."""
    lang_name = SUPPORTED_LANGS.get(source_lang, source_lang)

    prompt = f"""Translate the following {lang_name} phrase to English.

Requirements:
- Translate naturally
- Preserve any placeholders like {{WORD}} exactly as-is
- Return ONLY the translated text, no explanations

{lang_name}: {text}
English:"""

    return call_ollama(model, prompt)


def evaluate_translation(
    original_en: str,
    translation_a: str,
    translation_b: str,
    backtrans_a: str,
    backtrans_b: str,
    target_lang: str
) -> Dict:
    """Use critic model to evaluate translation quality and route."""

    lang_name = SUPPORTED_LANGS.get(target_lang, target_lang)

    prompt = f"""You are a translation quality evaluator. Assess the following translation pair.

Original English: {original_en}

Translator A ({lang_name}): {translation_a}
Back-translation A: {backtrans_a}

Translator B ({lang_name}): {translation_b}
Back-translation B: {backtrans_b}

Evaluate based on:
1. Meaning preservation (is the original meaning intact?)
2. Tone appropriateness (neutral, educational, not childish/rude/sexual)
3. Placeholder integrity (are {{PLACEHOLDERS}} preserved?)
4. Agreement (do A and B roughly agree?)

Respond in JSON format:
{{
  "decision": "approved|needs_review|rejected",
  "confidence": 85,
  "selected": "A|B",
  "reason": "brief explanation",
  "risks": "any concerns or 'none'"
}}

JSON:"""

    response = call_ollama(CRITIC_MODEL, prompt, temperature=0.1)

    try:
        # Extract JSON from response (model might add extra text)
        json_start = response.find('{')
        json_end = response.rfind('}') + 1
        if json_start != -1 and json_end > json_start:
            json_str = response[json_start:json_end]
            evaluation = json.loads(json_str)
        else:
            raise ValueError("No JSON found in response")

        # Validate required fields
        if "decision" not in evaluation or "confidence" not in evaluation:
            raise ValueError("Missing required fields")

        return evaluation

    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"Failed to parse critic response: {e}")
        # Default to needs_review on parse failure
        return {
            "decision": "needs_review",
            "confidence": 0,
            "selected": "A",
            "reason": f"Critic response parsing failed: {str(e)}",
            "risks": "unparseable evaluation"
        }


def process_word(
    word_id: str,
    micro_context_en: str,
    target_lang: str,
    retry: bool = False
) -> Dict:
    """
    Process a single word through the full pipeline.

    Returns a dict with all translation data and routing decision.
    """
    logger.info(f"Processing '{word_id}' → {target_lang} (retry={retry})")

    # Step 1 & 2: Forward translation (A and B)
    logger.info("  Step 1/5: Translator A (Qwen)")
    translation_a = translate_forward(micro_context_en, target_lang, TRANSLATOR_A)

    logger.info("  Step 2/5: Translator B (LLaMA)")
    translation_b = translate_forward(micro_context_en, target_lang, TRANSLATOR_B)

    if not translation_a or not translation_b:
        logger.error("  Translation failed - aborting")
        return {
            "word_id": word_id,
            "target_lang": target_lang,
            "decision": "rejected",
            "reason": "Translation API failure"
        }

    # Step 3 & 4: Back-translation
    logger.info("  Step 3/5: Back-translate A")
    backtrans_a = translate_backward(translation_a, target_lang, TRANSLATOR_B)

    logger.info("  Step 4/5: Back-translate B")
    backtrans_b = translate_backward(translation_b, target_lang, TRANSLATOR_A)

    # Step 5: Critic evaluation
    logger.info("  Step 5/5: Critic evaluation")
    evaluation = evaluate_translation(
        micro_context_en,
        translation_a,
        translation_b,
        backtrans_a,
        backtrans_b,
        target_lang
    )

    # Assemble result
    result = {
        "word_id": word_id,
        "target_lang": target_lang,
        "original_en": micro_context_en,
        "translation_a": translation_a,
        "translation_b": translation_b,
        "backtrans_a": backtrans_a,
        "backtrans_b": backtrans_b,
        "evaluation": evaluation,
        "decision": evaluation.get("decision", "needs_review"),
        "selected": evaluation.get("selected", "A"),
        "timestamp": datetime.utcnow().isoformat(),
        "retry": retry
    }

    logger.info(f"  ✓ Decision: {result['decision']} (confidence: {evaluation.get('confidence', 0)}%)")

    return result


def save_result(result: Dict):
    """Save translation result to appropriate folder."""
    word_id = result["word_id"]
    lang = result["target_lang"]
    decision = result["decision"]
    selected = result["selected"]
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    # Save drafts
    draft_a_file = DRAFT_A_DIR / f"{word_id}_{lang}_A_{timestamp}.json"
    draft_b_file = DRAFT_B_DIR / f"{word_id}_{lang}_B_{timestamp}.json"

    with open(draft_a_file, 'w', encoding='utf-8') as f:
        json.dump({
            "translation": result["translation_a"],
            "backtrans": result["backtrans_a"]
        }, f, ensure_ascii=False, indent=2)

    with open(draft_b_file, 'w', encoding='utf-8') as f:
        json.dump({
            "translation": result["translation_b"],
            "backtrans": result["backtrans_b"]
        }, f, ensure_ascii=False, indent=2)

    # Save QC report
    qc_file = QC_DIR / f"{word_id}_{lang}_{timestamp}.json"
    with open(qc_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # Route to final destination
    if decision == "approved":
        final_dir = APPROVED_DIR
    elif decision == "needs_review":
        final_dir = REVIEW_DIR
    else:
        final_dir = REJECTED_DIR

    # Save selected translation
    final_file = final_dir / f"{word_id}_{lang}.json"
    final_translation = result[f"translation_{selected.lower()}"]

    with open(final_file, 'w', encoding='utf-8') as f:
        json.dump({
            "word_id": word_id,
            "target_lang": lang,
            "translation": final_translation,
            "source_en": result["original_en"],
            "confidence": result["evaluation"].get("confidence", 0),
            "timestamp": result["timestamp"]
        }, f, ensure_ascii=False, indent=2)

    logger.info(f"  Saved to: {final_dir.name}/{final_file.name}")


def retry_rejected(word_id: str, micro_context_en: str, target_lang: str) -> Dict:
    """Retry a rejected translation with stricter constraints."""
    logger.warning(f"Retrying {word_id} → {target_lang} with stricter constraints")

    # TODO: Could add temperature=0.1 or additional constraints
    result = process_word(word_id, micro_context_en, target_lang, retry=True)

    if result["decision"] == "rejected":
        logger.error(f"  Still rejected after retry - quarantining")

    return result


def main():
    parser = argparse.ArgumentParser(description="Vocab Translation QA Pipeline")
    parser.add_argument("--text", type=str, help="Single text to translate")
    parser.add_argument("--word-id", type=str, default="test", help="Word ID for single translation")
    parser.add_argument("--langs", type=str, default="es,vi,id", help="Comma-separated language codes")
    parser.add_argument("--batch", type=str, help="Path to JSON file with multiple words")
    parser.add_argument("--retry-rejected", action="store_true", help="Automatically retry rejected items")

    args = parser.parse_args()

    # Parse target languages
    target_langs = [lang.strip() for lang in args.langs.split(",")]

    # Validate languages
    for lang in target_langs:
        if lang not in SUPPORTED_LANGS:
            logger.error(f"Unsupported language: {lang}")
            return

    # Single text mode
    if args.text:
        logger.info(f"Processing single text: '{args.text}'")

        for lang in target_langs:
            result = process_word(args.word_id, args.text, lang)
            save_result(result)

            # Retry if rejected and flag is set
            if result["decision"] == "rejected" and args.retry_rejected:
                retry_result = retry_rejected(args.word_id, args.text, lang)
                save_result(retry_result)

        logger.info("✓ Processing complete")
        return

    # Batch mode
    if args.batch:
        batch_file = Path(args.batch)
        if not batch_file.exists():
            logger.error(f"Batch file not found: {batch_file}")
            return

        with open(batch_file, 'r', encoding='utf-8') as f:
            words = json.load(f)

        logger.info(f"Processing {len(words)} words from {batch_file}")

        for word_data in words:
            word_id = word_data.get("id") or word_data.get("word")
            micro_context = word_data.get("micro_context_en")

            if not word_id or not micro_context:
                logger.warning(f"Skipping invalid entry: {word_data}")
                continue

            for lang in target_langs:
                result = process_word(word_id, micro_context, lang)
                save_result(result)

                if result["decision"] == "rejected" and args.retry_rejected:
                    retry_result = retry_rejected(word_id, micro_context, lang)
                    save_result(retry_result)

        logger.info("✓ Batch processing complete")
        return

    # No input provided
    parser.print_help()


if __name__ == "__main__":
    main()
