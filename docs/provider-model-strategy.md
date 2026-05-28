# Dragonsuite Provider Model Strategy

## Goal

Dragonsuite apps should not hardcode provider model names when the user is choosing models or when the app simply needs the best available model for a task. Apps should ask the live provider account what is available, resolve by task intent, and fall back only when discovery is unavailable.

## Shared Module

Use `scripts/provider_models.py` for provider discovery and task-based model resolution.

Supported discovery paths:

- OpenAI: `models.list()`
- Google/Gemini: `genai.Client().models.list()`
- Anthropic: `models.list()`
- Ollama: `/api/tags`
- LM Studio: OpenAI-compatible `/v1/models`
- llama.cpp server: OpenAI-compatible `/v1/models`
- OpenRouter: OpenAI-compatible `/v1/models`

Discovery results are cached for a short TTL using `DRAGONSUITE_MODEL_CACHE_SECONDS` with a default of 300 seconds.

## Capability Shape

The shared module can emit records with:

- `provider`
- `model`
- `modality`
- `tasks`
- `endpoint_type`
- `source`
- `quality_tier`
- `cost_tier`
- `supports_streaming`
- `supports_images`
- `supports_video`

Apps can expose these records through `/api/status` or `/api/models`.

## Resolver Pattern

Apps should request intent instead of guessing model strings:

```python
from scripts import provider_models

model = provider_models.resolve_model("openai", "analysis")["model"]
image_model = provider_models.resolve_model("openai", "image_generation")["model"]
```

Current task mappings:

- `analysis` -> text, fast
- `prompt_cleanup` -> text, fast
- `chat` -> text, balanced
- `image_generation` -> image, best
- `image_edit` -> image, best
- `video_generation` -> video, fast
- `music_generation` -> audio, balanced

For fast text tasks, the resolver prefers mini/nano/flash-style models instead of the biggest visible model. For image generation, it prefers the newest visible image model.

## API Status Endpoint

Apps with model pickers should expose `/api/status` with the shared payload:

```python
provider_models.status_payload(
    app="App Name",
    brand="Seed 13 Productions",
    providers=["openai", "google"],
    default_provider="openai",
)
```

The payload includes:

- models grouped by modality and provider
- compatibility aliases: `prompt_models`, `image_models`, `video_models`, `audio_models`
- default prompt/image model choices
- discovery source per provider: `live` or `fallback`
- discovery errors
- capability records

## Provider Policy

- Use live discovery for user-facing model dropdowns.
- Use task-based resolver defaults for internal model choices.
- Pin exact dated model IDs only when reproducibility matters.
- Keep direct OpenAI/Google APIs for image, video, music, files, and provider-specific features.
- Use OpenRouter as an optional text provider, not a universal path for everything.
- Use OpenAI-compatible local endpoints for LM Studio and llama.cpp when available.
- Query Ollama installed models instead of assuming names.

## Migrated Apps

- FrameForge: uses shared provider discovery for OpenAI and Google prompt/image dropdowns.
- CoverSynth OpenAI: uses shared OpenAI discovery for analysis model picker and image model default.
- The Movies: uses shared Google discovery/resolver for text and image models, with resolver-backed video/audio preview fallbacks.
- DragonArt: exposes shared OpenAI/Google image model discovery through `/api/config` and `/api/status`, and resolves image edit models at call time.
- DragonGlass: resolves Gemini image edit model through shared Google discovery and exposes shared status data.
- Anthropic utilities: `analyze_conversations.py`, `synthesize_lessons.py`, and `dragonclawd_server.py` resolve Claude models through shared Anthropic discovery while honoring `ANTHROPIC_MODEL`.
- Local Ollama utilities: `file_watcher.py`, `kb_compiler.py`, and `vocab_translate_qa.py` query installed Ollama models through the resolver while honoring their existing environment overrides.

## Next Migration Targets

1. Broaden migrations to any newly active apps found by `scripts/provider_inventory.py`.
2. Where useful, add UI model pickers to apps that currently resolve models internally but do not expose a selector.
3. Retire deprecated API callers rather than continuing to maintain reference-only servers.

## Known Current Findings

Live discovery on udragon showed:

- OpenAI text includes `gpt-5.5`, `gpt-5.4`, `gpt-5.4-mini`, `gpt-5.4-nano`, `gpt-5.2`, and older compatible models.
- OpenAI image includes `gpt-image-2`, `gpt-image-1.5`, `gpt-image-1`, and `gpt-image-1-mini`.
- Google text includes `gemini-3.5-flash`, `gemini-3.1-pro-preview`, `gemini-3.1-flash-lite`, `gemini-3-flash-preview`, and `gemini-2.5-flash`.
- Google image includes `gemini-3.1-flash-image-preview`, `gemini-3-pro-image-preview`, and `gemini-2.5-flash-image`.
- Anthropic includes `claude-sonnet-4-6`, `claude-opus-4-7`, and related current models.

## Error Reporting

Use `provider_models.classify_error(error)` or `provider_models.error_payload(error)` for user-visible provider failures. Current categories:

- `moderation_or_safety`
- `quota_or_billing`
- `auth_or_key`
- `model_unavailable`
- `network_or_timeout`
- `endpoint_unsupported`
- `provider_error`

FrameForge logs per-job `error_category`; CoverSynth OpenAI and DragonArt return categorized JSON errors.

## Validation Checklist

Inventory helper:

```bash
cd /srv/containers/edq
venv_dragonsuite/bin/python scripts/provider_inventory.py
```

For each migrated app:

- `/api/status` returns live or clearly marked fallback model data.
- UI dropdowns are populated from `/api/status` instead of static guesses.
- Internal calls resolve models by task intent.
- Missing key or provider outage produces a visible fallback/error field.
- One dry-run or non-destructive smoke test verifies the selected model path.
