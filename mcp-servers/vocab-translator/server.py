#!/usr/bin/env python3
"""
Vocab Translator MCP Server

Translation QA Pipeline for ESL Vocabulary Project
- Translator A: Qwen (es, vi, id)
- Translator B: LLaMA (es, vi, id)
- Critic: DeepSeek-R1 (QA decision)

Models run via Ollama (localhost:11434)
"""

import asyncio
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import aiohttp
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Configuration
PROJECT_BASE = Path("/home/edq/projects/vocab-project")
TRANSLATIONS_DIR = PROJECT_BASE / "translations"
DATA_DIR = PROJECT_BASE / "data"

# Ollama API
OLLAMA_BASE = "http://localhost:11434"

# Model assignments
MODELS = {
    "translator_a": "qwen3:8b",
    "translator_b": "llama3.2:latest",
    "critic": "deepseek-r1:14b",
}

# Supported languages
SUPPORTED_LANGS = {
    "es": "Spanish",
    "vi": "Vietnamese",
    "id": "Indonesian",
}

# Approval thresholds
CONFIDENCE_APPROVE = 85
CONFIDENCE_REVIEW = 70


async def call_ollama(model: str, prompt: str, system: str = "") -> dict[str, Any]:
    """Call Ollama API with a model."""
    async with aiohttp.ClientSession() as session:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
        }
        if system:
            payload["system"] = system

        async with session.post(
            f"{OLLAMA_BASE}/api/generate", json=payload, timeout=aiohttp.ClientTimeout(total=300)
        ) as resp:
            if resp.status != 200:
                raise Exception(f"Ollama error: {resp.status}")
            return await resp.json()


async def translate_text(text: str, target_lang: str, model: str) -> str:
    """Translate text to target language using specified model."""
    system = f"""You are a professional translator specializing in ESL (English as Second Language) vocabulary learning.
Translate the English text to {SUPPORTED_LANGS.get(target_lang, target_lang)} using simple, natural language.
Keep micro-context phrases short and learner-friendly.
Only output the translated text, nothing else."""

    result = await call_ollama(model, text, system=system)
    return result.get("response", "").strip()


async def back_translate(text: str, source_lang: str, model: str) -> str:
    """Back-translate text from target language to English."""
    system = f"""You are a professional translator. Back-translate the {SUPPORTED_LANGS.get(source_lang, source_lang)} text to English.
Keep the phrasing natural and accurate.
Only output the English translation, nothing else."""

    result = await call_ollama(model, text, system=system)
    return result.get("response", "").strip()


async def evaluate_translations(
    original: str,
    translation_a: str,
    translation_b: str,
    back_a: str,
    back_b: str,
    target_lang: str,
) -> dict[str, Any]:
    """Have the critic evaluate both translations."""
    prompt = f"""Evaluate two translations of an ESL vocabulary micro-context phrase.

TARGET LANGUAGE: {SUPPORTED_LANGS.get(target_lang, target_lang)}

ORIGINAL (English):
"{original}"

TRANSLATION A:
"{translation_a}"

BACK-TRANSLATION A:
"{back_a}"

TRANSLATION B:
"{translation_b}"

BACK-TRANSLATION B:
"{back_b}"

Evaluate on these criteria:
1. Meaning preserved (original vs back-translation drift)
2. Tone is neutral and age-appropriate
3. No risk terms (slang, childish, sexual, rude)
4. Placeholder {{}} integrity
5. Learner-friendly simplicity

Output JSON:
{{
  "preferred": "A" or "B",
  "confidence": 0-100,
  "meaning_preserved": true/false,
  "tone_neutral": true/false,
  "no_risk_terms": true/false,
  "placeholders_intact": true/false,
  "notes": "brief reasoning"
}}"""

    result = await call_ollama(MODELS["critic"], prompt)
    response_text = result.get("response", "").strip()

    # Extract JSON from response
    try:
        json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except json.JSONDecodeError:
        pass

    return {
        "preferred": "A",
        "confidence": 50,
        "meaning_preserved": False,
        "tone_neutral": False,
        "no_risk_terms": False,
        "placeholders_intact": False,
        "notes": "Parse error",
    }


async def process_word(word_data: dict[str, Any], target_lang: str) -> dict[str, Any]:
    """Full translation pipeline for a word."""
    word_id = word_data.get("id", "unknown")
    original = word_data.get("micro_context_en", "")

    if not original:
        return {"id": word_id, "error": "No English micro-context provided"}

    # Phase 1: Translate with both models
    try:
        translation_a = await translate_text(original, target_lang, MODELS["translator_a"])
        translation_b = await translate_text(original, target_lang, MODELS["translator_b"])
    except Exception as e:
        return {"id": word_id, "error": f"Translation phase failed: {e}"}

    # Phase 2: Back-translate
    try:
        back_a = await back_translate(translation_a, target_lang, MODELS["translator_a"])
        back_b = await back_translate(translation_b, target_lang, MODELS["translator_b"])
    except Exception as e:
        return {"id": word_id, "error": f"Back-translation phase failed: {e}"}

    # Phase 3: Critic evaluation
    try:
        eval_result = await evaluate_translations(
            original, translation_a, translation_b, back_a, back_b, target_lang
        )
    except Exception as e:
        return {"id": word_id, "error": f"Evaluation phase failed: {e}"}

    # Phase 4: Route to folder
    confidence = eval_result.get("confidence", 0)
    preferred = eval_result.get("preferred", "A")
    final_translation = translation_a if preferred == "A" else translation_b

    if confidence >= CONFIDENCE_APPROVE:
        status = "approved"
    elif confidence >= CONFIDENCE_REVIEW:
        status = "needs_review"
    else:
        status = "rejected"

    result = {
        "id": word_id,
        "lang": target_lang,
        "original": original,
        "translation_a": translation_a,
        "translation_b": translation_b,
        "back_a": back_a,
        "back_b": back_b,
        "final_translation": final_translation,
        "preferred": preferred,
        "confidence": confidence,
        "status": status,
        "eval": eval_result,
    }

    # Save to appropriate folder
    output_dir = TRANSLATIONS_DIR / status
    output_file = output_dir / f"{word_id}_{target_lang}.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(result, indent=2))

    return result


server = Server("vocab-translator")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="translate_word",
            description="Translate a vocabulary word's micro-context through full QA pipeline",
            inputSchema={
                "type": "object",
                "properties": {
                    "word_id": {"type": "string", "description": "Word identifier"},
                    "micro_context_en": {
                        "type": "string",
                        "description": "English micro-context phrase",
                    },
                    "target_lang": {
                        "type": "string",
                        "enum": list(SUPPORTED_LANGS.keys()),
                        "description": "Target language code",
                    },
                },
                "required": ["word_id", "micro_context_en", "target_lang"],
            },
        ),
        Tool(
            name="batch_translate",
            description="Translate multiple words to multiple languages",
            inputSchema={
                "type": "object",
                "properties": {
                    "words_json": {
                        "type": "string",
                        "description": "JSON array of word objects with id, micro_context_en",
                    },
                    "target_langs": {
                        "type": "array",
                        "items": {"type": "string", "enum": list(SUPPORTED_LANGS.keys())},
                        "description": "Target language codes",
                    },
                },
                "required": ["words_json", "target_langs"],
            },
        ),
        Tool(
            name="list_translations",
            description="List translations by status (approved, needs_review, rejected)",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["approved", "needs_review", "rejected", "all"],
                        "description": "Status filter",
                    }
                },
                "required": ["status"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Execute a tool."""
    if name == "translate_word":
        word_data = {
            "id": arguments["word_id"],
            "micro_context_en": arguments["micro_context_en"],
        }
        target_lang = arguments["target_lang"]
        result = await process_word(word_data, target_lang)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "batch_translate":
        words = json.loads(arguments["words_json"])
        target_langs = arguments["target_langs"]
        results = []

        for word in words:
            for lang in target_langs:
                result = await process_word(word, lang)
                results.append(result)

        return [TextContent(type="text", text=json.dumps(results, indent=2))]

    elif name == "list_translations":
        status = arguments["status"]
        results = {}

        if status == "all":
            statuses = ["approved", "needs_review", "rejected"]
        else:
            statuses = [status]

        for s in statuses:
            status_dir = TRANSLATIONS_DIR / s
            if status_dir.exists():
                files = list(status_dir.glob("*.json"))
                results[s] = [f.stem for f in files]
            else:
                results[s] = []

        return [TextContent(type="text", text=json.dumps(results, indent=2))]

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    """Run the server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="vocab-translator",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
