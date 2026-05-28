#!/usr/bin/env python3
"""Shared provider model discovery and lightweight task resolver for Dragonsuite.

The goal is to keep app UIs honest: list models the current keys/local servers can
actually see, then fall back to conservative defaults when discovery is unavailable.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
import re
import time
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional in tiny scripts
    load_dotenv = None

if load_dotenv:
    load_dotenv('/srv/containers/edq/.env')

CACHE_TTL_SECONDS = int(os.getenv('DRAGONSUITE_MODEL_CACHE_SECONDS', '300'))
_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}

PROVIDERS = ['openai', 'google', 'anthropic', 'openrouter', 'ollama', 'lmstudio', 'llamacpp']

FALLBACKS = {
    'openai': {
        'text': ['gpt-5.5', 'gpt-5.4', 'gpt-5.4-mini', 'gpt-5.4-nano', 'gpt-5.2', 'gpt-5', 'gpt-4.1-mini'],
        'image': ['gpt-image-2', 'gpt-image-1.5', 'gpt-image-1', 'gpt-image-1-mini'],
    },
    'google': {
        'text': ['gemini-3.5-flash', 'gemini-3.1-pro-preview', 'gemini-3.1-flash-lite', 'gemini-3-flash-preview', 'gemini-2.5-flash', 'gemini-2.5-pro'],
        'image': ['gemini-3.1-flash-image-preview', 'gemini-3-pro-image-preview', 'gemini-2.5-flash-image'],
        'video': ['veo-3.1-fast-generate-preview'],
        'audio': ['models/lyria-realtime-exp'],
    },
    'anthropic': {
        'text': ['claude-sonnet-4-6', 'claude-opus-4-7', 'claude-haiku-4-5-20251001'],
    },
    'openrouter': {'text': []},
    'ollama': {'text': []},
    'lmstudio': {'text': []},
    'llamacpp': {'text': []},
}

PREFERRED = {
    'openai': {
        'text': ['gpt-5.5', 'gpt-5.4', 'gpt-5.4-mini', 'gpt-5.4-nano', 'gpt-5.2', 'gpt-5.2-pro', 'gpt-5.1', 'gpt-5', 'gpt-5-mini', 'gpt-5-nano', 'gpt-4.1', 'gpt-4.1-mini', 'gpt-4.1-nano'],
        'image': ['gpt-image-2', 'gpt-image-1.5', 'gpt-image-1', 'gpt-image-1-mini'],
    },
    'google': {
        'text': ['gemini-3.5-flash', 'gemini-3.1-pro-preview', 'gemini-3.1-flash-lite', 'gemini-3-flash-preview', 'gemini-2.5-flash', 'gemini-2.5-pro', 'gemini-flash-latest', 'gemini-pro-latest'],
        'image': ['gemini-3.1-flash-image-preview', 'gemini-3-pro-image-preview', 'gemini-2.5-flash-image'],
        'video': ['veo-3.1-fast-generate-preview'],
        'audio': ['models/lyria-realtime-exp'],
    },
    'anthropic': {
        'text': ['claude-sonnet-4-6', 'claude-opus-4-7', 'claude-opus-4-6', 'claude-haiku-4-5-20251001', 'claude-sonnet-4-5-20250929'],
    },
}

TASK_DEFAULTS = {
    'prompt_cleanup': ('text', 'fast'),
    'analysis': ('text', 'fast'),
    'chat': ('text', 'balanced'),
    'image_generation': ('image', 'best'),
    'image_edit': ('image', 'best'),
    'video_generation': ('video', 'fast'),
    'music_generation': ('audio', 'balanced'),
}

@dataclass
class ModelInfo:
    provider: str
    model: str
    modality: str
    tasks: list[str]
    endpoint_type: str
    source: str
    quality_tier: str = 'balanced'
    cost_tier: str = 'unknown'
    supports_streaming: bool = False
    supports_images: bool = False
    supports_video: bool = False


def _ordered_subset(values: list[str], preferred: list[str]) -> list[str]:
    seen = set(values)
    result = [item for item in preferred if item in seen]
    result.extend(item for item in values if item not in result)
    return result


def _cached(key: str):
    item = _CACHE.get(key)
    if not item:
        return None
    ts, payload = item
    if time.time() - ts > CACHE_TTL_SECONDS:
        return None
    return payload


def _store(key: str, payload: dict[str, Any]) -> dict[str, Any]:
    _CACHE[key] = (time.time(), payload)
    return payload


def _http_json(url: str, headers: dict[str, str] | None = None, timeout: int = 5) -> Any:
    req = Request(url, headers=headers or {})
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8'))


def _openai_discover() -> dict[str, Any]:
    try:
        from openai import OpenAI
        ids = sorted(model.id for model in OpenAI(api_key=os.getenv('OPENAI_API_KEY')).models.list().data)
        text = [m for m in ids if re.match(r'^gpt-(?:5(?:\.\d+)?(?:-(?:mini|nano|pro))?|4\.1(?:-(?:mini|nano))?)$', m)]
        image = [m for m in ids if re.match(r'^gpt-image-(?:2|1\.5|1(?:-mini)?)$', m)]
        models = {
            'text': _ordered_subset(text, PREFERRED['openai']['text']),
            'image': _ordered_subset(image, PREFERRED['openai']['image']),
        }
        source = 'live'
        error = None
    except Exception as exc:
        models = dict(FALLBACKS['openai'])
        source = 'fallback'
        error = str(exc)
    for modality, fallback in FALLBACKS['openai'].items():
        if not models.get(modality):
            models[modality] = fallback
    return {'provider': 'openai', 'models': models, 'source': source, 'error': error}


def _google_discover() -> dict[str, Any]:
    try:
        from google import genai
        api_key = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
        if not api_key:
            raise RuntimeError('GOOGLE_API_KEY/GEMINI_API_KEY not configured')
        client = genai.Client(api_key=api_key)
        text: list[str] = []
        image: list[str] = []
        for model in client.models.list():
            model_id = (getattr(model, 'name', '') or '').split('/')[-1]
            actions = set(getattr(model, 'supported_actions', None) or getattr(model, 'supported_generation_methods', None) or [])
            if 'generateContent' not in actions or not model_id.startswith('gemini-'):
                continue
            if ('image' in model_id and 'preview' in model_id) or model_id == 'gemini-2.5-flash-image':
                image.append(model_id)
            elif all(token not in model_id for token in ('image', 'tts', 'audio', 'live', 'robotics', 'computer-use', 'embedding', 'customtools')):
                text.append(model_id)
        models = {
            'text': _ordered_subset(text, PREFERRED['google']['text']),
            'image': _ordered_subset(image, PREFERRED['google']['image']),
            'video': FALLBACKS['google']['video'],
            'audio': FALLBACKS['google']['audio'],
        }
        source = 'live'
        error = None
    except Exception as exc:
        models = dict(FALLBACKS['google'])
        source = 'fallback'
        error = str(exc)
    for modality, fallback in FALLBACKS['google'].items():
        if not models.get(modality):
            models[modality] = fallback
    return {'provider': 'google', 'models': models, 'source': source, 'error': error}


def _anthropic_discover() -> dict[str, Any]:
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        ids = [model.id for model in client.models.list(limit=100).data]
        models = {'text': _ordered_subset(ids, PREFERRED['anthropic']['text'])}
        source = 'live'
        error = None
    except Exception as exc:
        models = dict(FALLBACKS['anthropic'])
        source = 'fallback'
        error = str(exc)
    return {'provider': 'anthropic', 'models': models, 'source': source, 'error': error}


def _openai_compatible_discover(provider: str, base_url: str, api_key: str | None = None) -> dict[str, Any]:
    headers = {'Authorization': f'Bearer {api_key}'} if api_key else {}
    try:
        data = _http_json(base_url.rstrip('/') + '/v1/models', headers=headers)
        ids = [item.get('id') for item in data.get('data', []) if item.get('id')]
        source = 'live'
        error = None
    except Exception as exc:
        ids = []
        source = 'fallback'
        error = str(exc)
    return {'provider': provider, 'models': {'text': ids or FALLBACKS.get(provider, {}).get('text', [])}, 'source': source, 'error': error}


def _ollama_discover() -> dict[str, Any]:
    url = os.getenv('OLLAMA_URL', 'http://127.0.0.1:11434').rstrip('/')
    try:
        data = _http_json(url + '/api/tags')
        ids = [item.get('name') for item in data.get('models', []) if item.get('name')]
        source = 'live'
        error = None
    except Exception as exc:
        ids = []
        source = 'fallback'
        error = str(exc)
    return {'provider': 'ollama', 'models': {'text': ids}, 'source': source, 'error': error}



def classify_error(error: Any) -> str:
    text = str(error or '').lower()
    if any(token in text for token in ('moderation', 'safety', 'policy', 'blocked')):
        return 'moderation_or_safety'
    if any(token in text for token in ('quota', 'billing', 'hard limit', 'insufficient_quota', 'rate limit', '429')):
        return 'quota_or_billing'
    if any(token in text for token in ('api key', 'unauthorized', 'forbidden', '401', '403', 'auth')):
        return 'auth_or_key'
    if any(token in text for token in ('model not found', 'does not exist', 'not available', 'unsupported model')):
        return 'model_unavailable'
    if any(token in text for token in ('timeout', 'timed out', 'connection', 'network', 'reset')):
        return 'network_or_timeout'
    if any(token in text for token in ('unsupported', 'endpoint', 'response_modalities', 'invalid request')):
        return 'endpoint_unsupported'
    return 'provider_error'


def error_payload(error: Any) -> dict[str, str]:
    return {'error': str(error), 'error_category': classify_error(error)}

def discover_provider(provider: str, force: bool = False) -> dict[str, Any]:
    provider = provider.lower()
    key = f'provider:{provider}'
    if not force:
        cached = _cached(key)
        if cached:
            return cached
    if provider == 'openai':
        payload = _openai_discover()
    elif provider == 'google':
        payload = _google_discover()
    elif provider == 'anthropic':
        payload = _anthropic_discover()
    elif provider == 'ollama':
        payload = _ollama_discover()
    elif provider == 'lmstudio':
        payload = _openai_compatible_discover('lmstudio', os.getenv('LM_STUDIO_BASE_URL', 'http://127.0.0.1:1234'))
    elif provider == 'llamacpp':
        payload = _openai_compatible_discover('llamacpp', os.getenv('LLAMACPP_BASE_URL', 'http://127.0.0.1:8080'))
    elif provider == 'openrouter':
        payload = _openai_compatible_discover('openrouter', 'https://openrouter.ai/api', os.getenv('OPENROUTER_API_KEY'))
    else:
        payload = {'provider': provider, 'models': {}, 'source': 'fallback', 'error': f'Unknown provider {provider}'}
    return _store(key, payload)


def discover_all(providers: list[str] | None = None, force: bool = False) -> dict[str, Any]:
    providers = providers or PROVIDERS
    return {provider: discover_provider(provider, force=force) for provider in providers}


def models_for(provider: str, modality: str = 'text', force: bool = False) -> list[str]:
    return discover_provider(provider, force=force).get('models', {}).get(modality, [])


def _choose_by_tier(models: list[str], tier: str) -> str | None:
    if not models:
        return None
    if tier == 'fast':
        for token in ('mini', 'nano', 'flash-lite', 'flash'):
            for model in models:
                if token in model and 'image' not in model:
                    return model
    if tier == 'balanced':
        for model in models:
            if all(token not in model for token in ('pro', 'opus')):
                return model
    return models[0]


def resolve_model(provider: str, task: str = 'chat', modality: str | None = None, preferred: str | None = None, force: bool = False) -> dict[str, Any]:
    task_modality, tier = TASK_DEFAULTS.get(task, ('text', 'balanced'))
    modality = modality or task_modality
    models = models_for(provider, modality, force=force)
    if preferred and preferred in models:
        model = preferred
    else:
        model = _choose_by_tier(models, tier)
    if not model:
        fallback = FALLBACKS.get(provider, {}).get(modality, [])
        model = _choose_by_tier(fallback, tier)
    return {'provider': provider, 'task': task, 'modality': modality, 'tier': tier, 'model': model, 'candidates': models}


def capability_records(providers: list[str] | None = None, force: bool = False) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for provider, payload in discover_all(providers, force=force).items():
        source = payload.get('source', 'unknown')
        for modality, model_ids in payload.get('models', {}).items():
            for model_id in model_ids:
                records.append(asdict(ModelInfo(
                    provider=provider,
                    model=model_id,
                    modality=modality,
                    tasks=[task for task, (task_modality, _tier) in TASK_DEFAULTS.items() if task_modality == modality],
                    endpoint_type='openai-compatible' if provider in {'openrouter', 'lmstudio', 'llamacpp'} else provider,
                    source=source,
                    supports_images=modality == 'image',
                    supports_video=modality == 'video',
                )))
    return records


def status_payload(app: str, brand: str | None = None, providers: list[str] | None = None, default_provider: str = 'openai') -> dict[str, Any]:
    providers = providers or ['openai', 'google', 'anthropic', 'ollama', 'lmstudio', 'llamacpp', 'openrouter']
    discovered = discover_all(providers)
    models_by_modality: dict[str, dict[str, list[str]]] = {}
    sources: dict[str, str] = {}
    errors: dict[str, str] = {}
    for provider, payload in discovered.items():
        sources[provider] = payload.get('source', 'unknown')
        if payload.get('error'):
            errors[provider] = payload['error']
        for modality, models in payload.get('models', {}).items():
            models_by_modality.setdefault(modality, {})[provider] = models
    default_text = resolve_model(default_provider, 'analysis')
    default_image = resolve_model(default_provider, 'image_generation')
    return {
        'app': app,
        'brand': brand,
        'providers': providers,
        'models': models_by_modality,
        'prompt_models': models_by_modality.get('text', {}),
        'image_models': models_by_modality.get('image', {}),
        'video_models': models_by_modality.get('video', {}),
        'audio_models': models_by_modality.get('audio', {}),
        'sources': sources,
        'errors': errors,
        'capabilities': capability_records(providers),
        'defaults': {
            'prompt_provider': default_provider,
            'image_provider': default_provider,
            'prompt_model': default_text.get('model'),
            'image_model': default_image.get('model'),
        },
    }
