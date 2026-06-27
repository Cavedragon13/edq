#!/usr/bin/env python3
import base64
import cgi
from io import BytesIO
import json
import os
import re
import shutil
import sys
import subprocess
import tempfile
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from openai import OpenAI

sys.path.insert(0, '/srv/containers/edq')
from scripts import provider_models

ROOT = Path(__file__).resolve().parent
HOME = Path.home()
LOG_DIR = HOME / "ai_generated" / "frameforge"
LOG_DIR.mkdir(parents=True, exist_ok=True)

APP_NAME = "FrameForge"
BRAND_NAME = "Seed 13 Productions"
DEFAULT_PROMPT_MODEL = "gpt-5.4-mini"
DEFAULT_IMAGE_MODEL = "gpt-image-2"
OPENAI_PROMPT_MODELS = ["gpt-5.4-mini", "gpt-5.4-nano", "gpt-5.2", "gpt-5", "gpt-4.1-mini"]
GEMINI_PROMPT_MODELS = ["gemini-3.5-flash", "gemini-3.1-pro-preview", "gemini-3.1-flash-lite", "gemini-3-flash-preview", "gemini-2.5-flash", "gemini-2.5-pro"]
PROMPT_MODELS = OPENAI_PROMPT_MODELS + GEMINI_PROMPT_MODELS
PROMPT_PROVIDER_MODELS = {"openai": OPENAI_PROMPT_MODELS, "google": GEMINI_PROMPT_MODELS}
OPENAI_IMAGE_MODELS = ["gpt-image-2"]
GEMINI_IMAGE_MODELS = ["gemini-3.1-flash-image-preview", "gemini-3-pro-image-preview", "gemini-2.5-flash-image"]
IMAGE_MODELS = OPENAI_IMAGE_MODELS + GEMINI_IMAGE_MODELS
IMAGE_PROVIDER_MODELS = {"openai": OPENAI_IMAGE_MODELS, "google": GEMINI_IMAGE_MODELS}
PROVIDERS = ["openai", "google"]
QUALITIES = {"low", "medium", "high"}
MAX_JOBS = 10

PROMPT_HEADER = """Create exactly ONE standalone image.

Do not create a collage, contact sheet, split panel, multiple scenes, or mood board unless explicitly requested.

Follow the requested aspect ratio and composition.

Use provided reference images only as described.

Preserve exact requested text if required_text exists.

Do not add random text, signatures, watermarks, or logos unless explicitly requested."""

load_dotenv("/srv/containers/edq/.env")
load_dotenv(ROOT / ".env", override=False)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=180)


def status_payload():
    return provider_models.status_payload(APP_NAME, BRAND_NAME, providers=PROVIDERS, default_provider='openai')


def clean_json(text):
    value = text or ""
    fenced = re.search(r"```(?:json)?\s*(.*?)```", value, re.S | re.I)
    if fenced:
        value = fenced.group(1)
    match = re.search(r"(\{.*\}|\[.*\])", value, re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def looks_like_local_path(text):
    value = (text or "").strip().strip('"')
    if "\n" in value or len(value) > 600:
        return False
    pathish = value.startswith(("/", "~/")) or re.match(r"^[A-Za-z]:[\\/]", value)
    return bool(pathish and re.search(r"\.(json|pdf|txt|csv|md|rtf)$", value, re.I))


def extract_pdf(data):
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name
    try:
        if subprocess.run(["which", "pdftotext"], capture_output=True).returncode == 0:
            result = subprocess.run(
                ["pdftotext", "-layout", tmp_path, "-"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        return ""
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def slugify(value, fallback="project"):
    slug = re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_")
    return slug[:80] or fallback


def normalize_filename(value, job_id):
    name = str(value or f"{job_id}.png").strip()
    stem = slugify(Path(name).stem, job_id)
    return f"{stem}.png"


def parse_jsonish(value):
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        parsed = json.loads(value)
        if isinstance(parsed, (dict, list)):
            return parsed
    raise ValueError("Manifest must be a JSON object or array")


def arrayify(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def normalize_size(value, default="1024x1024"):
    size = str(value or default).lower().replace(" ", "")
    return size if re.match(r"^\d{3,4}x\d{3,4}$", size) else default


def flow_steps(flow):
    steps = flow.get("sequence") or flow.get("images") or flow.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("JSON flow needs a non-empty sequence/images/steps array")
    return steps


def build_step_prompt(flow, step):
    defaults = flow.get("defaults") or {}
    parts = []
    for key in ("prompt_prefix", "style", "camera", "lighting", "palette", "constraints"):
        value = defaults.get(key)
        if isinstance(value, list):
            value = ", ".join(str(item) for item in value)
        if value:
            parts.append(str(value))
    for key in ("prompt", "description", "scene", "prompt_body"):
        if step.get(key):
            parts.append(str(step[key]))
            break
    for key in ("mood", "palette", "avoid", "negative_instructions"):
        value = step.get(key)
        if isinstance(value, list):
            value = ", ".join(str(item) for item in value)
        if value:
            label = "avoid" if key == "avoid" else key
            parts.append(f"{label}: {value}")
    if defaults.get("prompt_suffix"):
        parts.append(str(defaults["prompt_suffix"]))
    prompt = "\n".join(part for part in parts if part).strip()
    if not prompt:
        raise ValueError("Each job needs prompt_body, prompt, description, or scene")
    return prompt


def job_source(raw):
    if isinstance(raw, list):
        return raw, {}
    if not isinstance(raw, dict):
        raise ValueError("Manifest must be an object or an array of jobs")
    if isinstance(raw.get("jobs"), list):
        return raw["jobs"], raw
    for key in ("sequence", "images", "steps"):
        if isinstance(raw.get(key), list):
            jobs = []
            for step in raw[key]:
                item = dict(step)
                item.setdefault("prompt_body", build_step_prompt(raw, item))
                jobs.append(item)
            return jobs, raw
    return [], raw


def normalize_provider(value, default="openai"):
    provider = str(value or default).lower().strip()
    return provider if provider in PROVIDERS else default


def normalize_prompt_model(provider, value):
    provider = normalize_provider(provider)
    models = provider_models.models_for(provider, 'text') or PROMPT_PROVIDER_MODELS.get(provider, OPENAI_PROMPT_MODELS)
    resolved = provider_models.resolve_model(provider, 'analysis', preferred=str(value or ''))
    return str(value) if str(value or '') in models else (resolved.get('model') or models[0])


def normalize_image_model(provider, value):
    provider = normalize_provider(provider)
    models = provider_models.models_for(provider, 'image') or IMAGE_PROVIDER_MODELS.get(provider, OPENAI_IMAGE_MODELS)
    resolved = provider_models.resolve_model(provider, 'image_generation', preferred=str(value or ''))
    return str(value) if str(value or '') in models else (resolved.get('model') or models[0])


def normalize_manifest(value, options=None):
    options = options or {}
    raw = parse_jsonish(value)
    jobs_raw, source = job_source(raw)
    project = options.get("project") or source.get("project") or source.get("title") or "FrameForge Project"
    image_provider = normalize_provider(source.get("image_provider") or options.get("image_provider") or "openai")
    prompt_provider = normalize_provider(source.get("prompt_provider") or options.get("prompt_provider") or image_provider)
    default_prompt_model = normalize_prompt_model(prompt_provider, source.get("default_prompt_model") or options.get("prompt_model"))
    default_image_model = normalize_image_model(image_provider, source.get("default_image_model") or options.get("image_model"))
    default_quality = source.get("default_quality") or source.get("quality") or options.get("quality") or "high"
    if default_quality not in QUALITIES:
        default_quality = "high"
    default_size = normalize_size(source.get("default_size") or source.get("size") or options.get("size"))
    allow_text = source.get("allow_text_in_image")
    if allow_text is None:
        allow_text = options.get("allow_text_in_image", True)
    max_jobs = int(source.get("max_jobs") or MAX_JOBS)

    manifest = {
        "project": project,
        "brand": source.get("brand") or BRAND_NAME,
        "app": source.get("app") or APP_NAME,
        "prompt_provider": prompt_provider,
        "image_provider": image_provider,
        "default_prompt_model": default_prompt_model,
        "default_image_model": default_image_model,
        "default_quality": default_quality,
        "default_size": default_size,
        "allow_text_in_image": bool(allow_text),
        "prompts_cleaned": bool(source.get("prompts_cleaned") or source.get("prompt_cleaned")),
        "cleaned_at": source.get("cleaned_at"),
        "cleanup_model": source.get("cleanup_model"),
        "continue_on_error": source.get("continue_on_error", True) is not False,
        "max_jobs": max_jobs,
        "output_path": source.get("output_path") or f"ai_generated/{slugify(project, 'frameforge_project')}",
        "reference_images": source.get("reference_images") if isinstance(source.get("reference_images"), list) else [],
        "jobs": [],
    }

    for index, original in enumerate(jobs_raw, start=1):
        if not isinstance(original, dict):
            original = {"prompt_body": str(original)}
        title = original.get("title") or original.get("name") or f"Image {index:02d}"
        job_id = slugify(original.get("id") or f"{index:02d}_{title}", f"{index:02d}_image")
        prompt_body = (
            original.get("prompt_body")
            or original.get("prompt")
            or original.get("description")
            or original.get("scene")
            or ""
        )
        required_text = arrayify(original.get("required_text"))
        job = {
            "id": job_id,
            "title": str(title),
            "filename": normalize_filename(original.get("filename"), job_id),
            "size": normalize_size(original.get("size"), default_size),
            "quality": original.get("quality") if original.get("quality") in QUALITIES else default_quality,
            "required_text": required_text,
            "prompt_body": str(prompt_body).strip(),
            "negative_instructions": str(original.get("negative_instructions") or original.get("avoid") or "").strip(),
            "prompt_cleaned": bool(original.get("prompt_cleaned") or source.get("prompts_cleaned")),
            "reference_image_ids": arrayify(original.get("reference_image_ids")),
            "provider": normalize_provider(original.get("provider") or manifest["image_provider"], manifest["image_provider"]),
            "model": normalize_image_model(original.get("provider") or manifest["image_provider"], original.get("model") or manifest["default_image_model"]),
            "status": "queued",
        }
        manifest["jobs"].append(job)
    return manifest


def validate_manifest_data(manifest):
    errors = []
    warnings = []
    jobs = manifest.get("jobs") or []
    max_jobs = int(manifest.get("max_jobs") or MAX_JOBS)
    if len(jobs) < 1:
        errors.append("Manifest needs at least one job.")
    if len(jobs) > max_jobs:
        errors.append(f"Manifest has {len(jobs)} jobs; the current maximum is {max_jobs}.")

    seen = set()
    ref_ids = {str(ref.get("id")) for ref in manifest.get("reference_images", []) if isinstance(ref, dict) and ref.get("id")}
    for index, job in enumerate(jobs, start=1):
        job_id = job.get("id")
        if not job_id:
            errors.append(f"Job {index} is missing an id.")
        elif job_id in seen:
            errors.append(f"Duplicate job id: {job_id}.")
        seen.add(job_id)
        if not job.get("prompt_body"):
            errors.append(f"Job {job_id or index} needs prompt_body.")
        if not re.match(r"^[a-z0-9_][a-z0-9_.-]*\.png$", job.get("filename", "")):
            errors.append(f"Job {job_id or index} has an invalid filename.")
        size = job.get("size", "")
        if not re.match(r"^\d{3,4}x\d{3,4}$", size):
            errors.append(f"Job {job_id or index} has an invalid size.")
        for ref_id in job.get("reference_image_ids", []):
            if ref_ids and ref_id not in ref_ids:
                warnings.append(f"Job {job_id} references unknown image id {ref_id}.")

    for ref in manifest.get("reference_images", []):
        if not isinstance(ref, dict):
            warnings.append("Reference images should be objects.")
            continue
        path = ref.get("path")
        if path and not resolve_reference_path(path).exists():
            warnings.append(f"Reference asset not found: {path}.")

    plan = [
        {
            "id": job["id"],
            "title": job["title"],
            "filename": job["filename"],
            "size": job["size"],
            "quality": job["quality"],
            "provider": job.get("provider", manifest.get("image_provider", "openai")),
            "model": job["model"],
        }
        for job in jobs
    ]
    return {"valid": not errors, "errors": errors, "warnings": warnings, "plan": plan}


def resolve_output_path(manifest):
    output_path = Path(manifest.get("output_path") or f"ai_generated/{slugify(manifest.get('project'))}")
    if output_path.is_absolute():
        return output_path
    return HOME / output_path


def resolve_reference_path(path):
    ref_path = Path(str(path)).expanduser()
    if ref_path.is_absolute():
        return ref_path
    candidate = ROOT / ref_path
    if candidate.exists():
        return candidate
    return HOME / ref_path


def unique_path(path):
    if not path.exists():
        return path
    for revision in range(2, 1000):
        candidate = path.with_name(f"{path.stem}_v{revision}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise ValueError(f"Could not find a unique filename for {path.name}")


def build_generation_prompt(manifest, job):
    parts = [PROMPT_HEADER, job.get("prompt_body", "").strip()]
    required_text = job.get("required_text") or []
    if required_text:
        parts.append("Required exact text: " + "; ".join(required_text))
    else:
        parts.append("No extra text or random lettering.")
    if job.get("negative_instructions"):
        parts.append("Negative instructions: " + job["negative_instructions"])
    return "\n\n".join(part for part in parts if part)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def log_event(kind, payload):
    record = {"ts": datetime.now(timezone.utc).isoformat(), "kind": kind, **payload}
    with (LOG_DIR / "dragonsynth.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def log_safe_output(output):
    return {k: v for k, v in output.items() if k != "image"}


def copy_references(manifest, project_dir):
    copied = {}
    refs_dir = project_dir / "references"
    refs_dir.mkdir(parents=True, exist_ok=True)
    for ref in manifest.get("reference_images", []):
        if not isinstance(ref, dict) or not ref.get("id") or not ref.get("path"):
            continue
        src = resolve_reference_path(ref["path"])
        if not src.exists() or not src.is_file():
            continue
        dst = unique_path(refs_dir / normalize_filename(src.name, slugify(ref["id"], "reference")))
        shutil.copy2(src, dst)
        copied[str(ref["id"])] = dst
        ref["copied_path"] = str(dst)
    return copied


def first_reference_for_job(job, copied_refs):
    for ref_id in job.get("reference_image_ids", []):
        if ref_id in copied_refs:
            return copied_refs[ref_id]
    return None


def is_moderation_error(exc):
    text = str(exc).lower()
    return any(word in text for word in ("moderation", "safety", "policy"))


class Handler(BaseHTTPRequestHandler):
    def _headers(self, status=200, content_type="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _json(self, status, data):
        self._headers(status)
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def _body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length > 30 * 1024 * 1024:
            raise ValueError("Request body too large")
        return self.rfile.read(length)

    def do_OPTIONS(self):
        self._headers(204)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            path = "/index.html"
        if path == "/api/status":
            return self._json(200, status_payload())
        file_path = (ROOT / path.lstrip("/")).resolve()
        if not str(file_path).startswith(str(ROOT)) or not file_path.exists():
            return self._json(404, {"error": "Not found"})
        content_type = {
            ".html": "text/html",
            ".css": "text/css",
            ".js": "application/javascript",
            ".png": "image/png",
            ".svg": "image/svg+xml",
        }.get(file_path.suffix, "application/octet-stream")
        self._headers(200, content_type)
        self.wfile.write(file_path.read_bytes())

    def do_POST(self):
        try:
            path = urlparse(self.path).path
            if path == "/api/upload":
                return self.upload()
            data = json.loads(self._body().decode("utf-8") or "{}")
            if path == "/api/analyze":
                return self.analyze(data)
            if path == "/api/generate":
                return self.generate(data)
            if path == "/api/run-flow":
                return self.run_flow(data)
            if path == "/api/refine":
                return self.refine(data)
            if path == "/api/sanitize-manifest":
                return self.sanitize_manifest(data)
            if path == "/api/validate-manifest":
                return self.validate_manifest(data)
            if path == "/api/run-manifest":
                return self.run_manifest(data)
            return self._json(404, {"error": "Unknown endpoint"})
        except Exception as exc:
            return self._json(500, {"error": str(exc)})

    def upload(self):
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": self.headers.get("Content-Type")},
        )
        item = form["file"] if "file" in form else None
        if isinstance(item, list):
            item = item[0] if item else None
        if item is None or not getattr(item, "filename", ""):
            return self._json(400, {"error": "No file uploaded"})
        data = item.file.read()
        name = item.filename.lower()
        text = extract_pdf(data) if name.endswith(".pdf") else data.decode("utf-8", errors="replace")
        if not text.strip():
            return self._json(422, {"error": "I could not extract readable text from that file."})
        self._json(200, {"text": text, "filename": item.filename, "characters": len(text)})

    def analyze(self, data):
        playlist = (data.get("playlist") or "").strip()
        provider = normalize_provider(data.get("prompt_provider") or data.get("image_provider") or "openai")
        model = normalize_prompt_model(provider, data.get("model"))
        if not playlist:
            return self._json(400, {"error": "Add structured JSON or upload a JSON/text file first."})
        if looks_like_local_path(playlist):
            return self._json(400, {"error": "That looks like a file path, not file contents. Use the upload area so the browser sends the file to udragon."})

        prompt = f"""You are CoverSynth legacy JSON mode. Return compact JSON with keys: title, summary, dominant_moods, sentiment, genres, visual_motifs, color_palette, avoid, cover_prompt, track_notes.

The cover_prompt must describe one square playlist cover, no text/logos, suitable for GPT Image 2.

Input JSON or structured text:
{playlist[:24000]}"""
        raw = generate_prompt_text(provider, model, prompt)
        analysis = clean_json(raw) or {"summary": raw, "cover_prompt": raw}
        log_event("legacy-analysis", {"model": model, "analysis": analysis})
        self._json(200, {"model": model, "analysis": analysis, "raw": raw})

    def generate(self, data):
        prompt = (data.get("prompt") or "").strip()
        refinement = (data.get("refinement") or "").strip()
        quality = data.get("quality") if data.get("quality") in QUALITIES else "medium"
        if refinement:
            prompt = f"{prompt}\n\nRefinement request: {refinement}\nKeep the same playlist-cover concept unless the refinement says otherwise."
        if not prompt:
            return self._json(400, {"error": "Image prompt is required"})
        result = client.images.generate(
            model=DEFAULT_IMAGE_MODEL,
            prompt=prompt,
            size="1024x1024",
            quality=quality,
            output_format="png",
        )
        image_b64 = result.data[0].b64_json
        log_event("legacy-image", {"model": DEFAULT_IMAGE_MODEL, "quality": quality, "prompt": prompt})
        self._json(200, {"model": DEFAULT_IMAGE_MODEL, "image": image_b64, "prompt": prompt})

    def run_flow(self, data):
        flow = parse_jsonish(data.get("flow") or data.get("json") or data.get("playlist"))
        manifest = normalize_manifest(flow, {"quality": data.get("quality")})
        return self._run_manifest_response(manifest, bool(data.get("dry_run")))

    def refine(self, data):
        idea = (data.get("idea") or "").strip()
        if not idea:
            return self._json(400, {"error": "Idea is required."})
        count = max(1, min(MAX_JOBS, int(data.get("count") or 6)))
        project = data.get("project") or "FrameForge Project"
        image_provider = normalize_provider(data.get("image_provider") or "openai")
        prompt_provider = normalize_provider(data.get("prompt_provider") or image_provider)
        prompt_model = normalize_prompt_model(prompt_provider, data.get("prompt_model"))
        image_model = normalize_image_model(image_provider, data.get("image_model"))
        quality = data.get("quality") if data.get("quality") in QUALITIES else "high"
        size = normalize_size(data.get("size") or "1024x1024")
        allow_text = bool(data.get("allow_text_in_image", True))

        instruction = f"""Create a canonical {APP_NAME} manifest as JSON only.

Brand: {BRAND_NAME}
Project: {project}
Number of jobs: {count}
Default prompt provider: {prompt_provider}
Default image provider: {image_provider}
Default image model: {image_model}
Default size: {size}
Default quality: {quality}
Allow text in image: {allow_text}

Rules:
- Return one JSON object with the canonical manifest fields.
- Create exactly {count} independent jobs.
- Every job must describe ONE standalone image.
- Do not create collage, contact sheet, split-panel, mood-board, or multi-scene prompts unless the user's idea explicitly asks for that as a single image style.
- Use deterministic ids like 01_cover, 02_variant.
- Use lowercase ascii filenames.
- Put visual direction in prompt_body.
- Put forbidden details in negative_instructions.
- Preserve exact requested text in required_text.

User idea:
{idea[:20000]}"""
        raw = generate_prompt_text(prompt_provider, prompt_model, instruction)
        parsed = clean_json(raw)
        if parsed is None:
            return self._json(502, {"error": "Prompt model did not return JSON.", "raw": raw})
        manifest = normalize_manifest(
            parsed,
            {
                "project": project,
                "prompt_provider": prompt_provider,
                "prompt_model": prompt_model,
                "image_provider": image_provider,
                "image_model": image_model,
                "quality": quality,
                "size": size,
                "allow_text_in_image": allow_text,
            },
        )
        validation = validate_manifest_data(manifest)
        log_event("refine", {"model": prompt_model, "project": project, "jobs": len(manifest["jobs"]), "valid": validation["valid"]})
        self._json(200, {"manifest": manifest, "validation": validation, "raw": raw})


    def sanitize_manifest(self, data):
        manifest = normalize_manifest(
            data.get("manifest") or data.get("json") or data,
            {
                "project": data.get("project"),
                "quality": data.get("quality"),
                "size": data.get("size"),
                "prompt_provider": data.get("prompt_provider"),
                "prompt_model": data.get("prompt_model"),
                "image_provider": data.get("image_provider"),
                "image_model": data.get("image_model"),
                "allow_text_in_image": data.get("allow_text_in_image", True),
            },
        )
        prompt_provider = normalize_provider(data.get("prompt_provider") or manifest.get("prompt_provider") or data.get("image_provider") or manifest.get("image_provider") or "openai")
        prompt_model = normalize_prompt_model(prompt_provider, data.get("prompt_model") or manifest.get("default_prompt_model"))
        instruction = f"""Rewrite this {APP_NAME} image manifest as JSON only.

Goal: make every image prompt more likely to pass image API moderation while preserving the intended visual direction and sequence.

Rules:
- Preserve the canonical manifest structure, ids, titles, filenames, sizes, quality, required_text, provider, model, and output_path.
- Rewrite prompt_body and negative_instructions only when useful.
- Remove direct artist names, celebrity names, living-artist style requests, copyrighted character names, and phrases like "in the style of".
- Replace those references with observable visual language: era, medium, composition, camera, palette, lighting, texture, mood, genre, art movement, production design, typography style if text is allowed.
- Keep each job as ONE standalone image, not a collage or contact sheet, unless a job explicitly requests a collage as the subject.
- Keep policy/safety language out of the prompt bodies; make them read like natural art direction.

Manifest:
{json.dumps(manifest, ensure_ascii=False)[:30000]}
"""
        raw = generate_prompt_text(prompt_provider, prompt_model, instruction)
        parsed = clean_json(raw)
        if parsed is None:
            return self._json(502, {"error": "Prompt model did not return JSON.", "raw": raw})
        sanitized = normalize_manifest(parsed, {"prompt_provider": prompt_provider, "prompt_model": prompt_model})
        cleaned_at = datetime.now(timezone.utc).isoformat()
        sanitized["prompts_cleaned"] = True
        sanitized["cleaned_at"] = cleaned_at
        sanitized["cleanup_model"] = prompt_model
        for job in sanitized.get("jobs", []):
            job["prompt_cleaned"] = True
        validation = validate_manifest_data(sanitized)
        log_event("sanitize", {"model": prompt_model, "project": sanitized.get("project"), "jobs": len(sanitized.get("jobs", [])), "valid": validation["valid"], "cleaned_at": cleaned_at})
        self._json(200, {"manifest": sanitized, "validation": validation, "raw": raw})

    def validate_manifest(self, data):
        manifest = normalize_manifest(
            data.get("manifest") or data.get("json") or data,
            {
                "project": data.get("project"),
                "quality": data.get("quality"),
                "size": data.get("size"),
                "prompt_provider": data.get("prompt_provider"),
                "prompt_model": data.get("prompt_model"),
                "image_provider": data.get("image_provider"),
                "image_model": data.get("image_model"),
                "allow_text_in_image": data.get("allow_text_in_image", True),
            },
        )
        validation = validate_manifest_data(manifest)
        self._json(200, {"manifest": manifest, "validation": validation})

    def run_manifest(self, data):
        manifest = normalize_manifest(data.get("manifest") or data.get("json") or data)
        validation = validate_manifest_data(manifest)
        if not validation["valid"]:
            return self._json(422, {"manifest": manifest, "validation": validation})
        dry_run = bool(data.get("dry_run"))
        selected = set(arrayify(data.get("selected_ids")))
        return self._run_manifest_response(manifest, dry_run, selected)

    def _run_manifest_response(self, manifest, dry_run=False, selected=None):
        selected = selected or set()
        result = execute_manifest(manifest, dry_run=dry_run, selected_ids=selected)
        status = 200 if not result.get("fatal_error") else 500
        self._json(status, result)




def generate_prompt_text(provider, model, instruction):
    provider = normalize_provider(provider)
    if provider == "google":
        try:
            from google import genai
        except ImportError as exc:
            raise RuntimeError("google-genai SDK is not installed for Gemini prompting") from exc
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY is not configured for Gemini prompting")
        google_client = genai.Client(api_key=api_key)
        response = google_client.models.generate_content(model=model, contents=instruction)
        return getattr(response, "text", "") or ""
    response = client.responses.create(model=model, input=instruction)
    return getattr(response, "output_text", "") or ""

def generate_openai_image(job, prompt, ref_path=None):
    if ref_path:
        with ref_path.open("rb") as image_file:
            result = client.images.edit(
                model=job["model"],
                image=(ref_path.name, BytesIO(image_file.read()), "image/png"),
                prompt=prompt,
                size=job["size"],
                quality=job["quality"],
            )
    else:
        result = client.images.generate(
            model=job["model"],
            prompt=prompt,
            size=job["size"],
            quality=job["quality"],
            output_format="png",
        )
    return result.data[0].b64_json, {"created": getattr(result, "created", None)}


def generate_google_image(job, prompt, ref_path=None):
    try:
        from google import genai
        from google.genai import types as genai_types
    except ImportError as exc:
        raise RuntimeError("google-genai SDK is not installed for Gemini image generation") from exc
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is not configured for Gemini image generation")
    google_client = genai.Client(api_key=api_key)
    parts = []
    if ref_path:
        mime = "image/jpeg" if ref_path.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
        parts.append(genai_types.Part.from_bytes(data=ref_path.read_bytes(), mime_type=mime))
    parts.append(genai_types.Part.from_text(text=prompt))
    response = google_client.models.generate_content(
        model=job["model"],
        contents=parts,
        config=genai_types.GenerateContentConfig(response_modalities=["IMAGE"]),
    )
    try:
        parts_out = response.candidates[0].content.parts
    except Exception as exc:
        raise RuntimeError("Gemini returned no image candidate") from exc
    for part in parts_out:
        inline = getattr(part, "inline_data", None)
        if inline:
            return base64.b64encode(inline.data).decode(), {"mime_type": inline.mime_type}
    text = " ".join(getattr(part, "text", "") for part in parts_out if getattr(part, "text", ""))
    raise RuntimeError(text or "Gemini returned no image data")


def generate_job_image(job, prompt, ref_path=None):
    provider = normalize_provider(job.get("provider"))
    if provider == "google":
        return generate_google_image(job, prompt, ref_path)
    return generate_openai_image(job, prompt, ref_path)

def execute_manifest(manifest, dry_run=False, selected_ids=None):
    selected_ids = selected_ids or set()
    project_dir = resolve_output_path(manifest)
    jobs_dir = project_dir / "jobs"
    images_dir = project_dir / "images"
    logs_dir = project_dir / "logs"
    for folder in (jobs_dir, images_dir, logs_dir):
        folder.mkdir(parents=True, exist_ok=True)

    write_json(project_dir / "manifest.json", manifest)
    copied_refs = copy_references(manifest, project_dir)
    outputs = []
    run_log = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "project": manifest["project"],
        "dry_run": dry_run,
        "selected_ids": sorted(selected_ids),
        "jobs": [],
    }
    log_event("run-start", {
        "project": manifest["project"],
        "dry_run": dry_run,
        "selected_ids": sorted(selected_ids),
        "job_count": len(manifest["jobs"]),
    })

    for job in manifest["jobs"]:
        if selected_ids and job["id"] not in selected_ids:
            skipped = {**job, "status": "skipped"}
            outputs.append(skipped)
            run_log["jobs"].append({"id": job["id"], "status": "skipped"})
            continue

        prompt = build_generation_prompt(manifest, job)
        output = {
            "id": job["id"],
            "title": job["title"],
            "filename": job["filename"],
            "provider": job["provider"],
            "model": job["model"],
            "size": job["size"],
            "quality": job["quality"],
            "status": "queued",
            "prompt": prompt,
        }
        try:
            output["status"] = "running"
            output["timestamp"] = datetime.now(timezone.utc).isoformat()
            write_json(jobs_dir / f"{job['id']}.json", log_safe_output(output))
            log_event("job-start", {
                "project": manifest["project"],
                "job": log_safe_output(output),
            })
            if dry_run:
                output["status"] = "complete"
                output["dry_run"] = True
            else:
                ref_path = first_reference_for_job(job, copied_refs)
                image_b64, api_metadata = generate_job_image(job, prompt, ref_path)
                image_path = unique_path(images_dir / job["filename"])
                image_path.write_bytes(base64.b64decode(image_b64))
                output["filename"] = image_path.name
                output["path"] = str(image_path)
                output["image"] = image_b64
                output["status"] = "complete"
                output["api_metadata"] = api_metadata
            metadata = {**output}
            metadata.pop("image", None)
            metadata["timestamp"] = datetime.now(timezone.utc).isoformat()
            write_json(jobs_dir / f"{job['id']}.json", metadata)
            run_log["jobs"].append(metadata)
            log_event("job-complete", {
                "project": manifest["project"],
                "job": metadata,
            })
        except Exception as exc:
            output["status"] = "moderated" if is_moderation_error(exc) else "failed"
            output["error"] = str(exc)
            output["error_category"] = provider_models.classify_error(exc)
            output["timestamp"] = datetime.now(timezone.utc).isoformat()
            safe_output = log_safe_output(output)
            write_json(jobs_dir / f"{job['id']}.json", safe_output)
            run_log["jobs"].append(safe_output)
            log_event("job-error", {
                "project": manifest["project"],
                "job": safe_output,
            })
            if not manifest.get("continue_on_error", True):
                outputs.append(output)
                break
        outputs.append(output)
        run_log["updated_at"] = datetime.now(timezone.utc).isoformat()
        write_json(project_dir / "run_log.json", run_log)

    run_log["finished_at"] = datetime.now(timezone.utc).isoformat()
    write_json(project_dir / "run_log.json", run_log)
    log_event("manifest-run", {"project": manifest["project"], "dry_run": dry_run, "outputs": [log_safe_output(item) for item in outputs]})
    return {
        "app": APP_NAME,
        "brand": BRAND_NAME,
        "project_dir": str(project_dir),
        "dry_run": dry_run,
        "manifest": manifest,
        "outputs": outputs,
    }


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8054"))
    print(f"{APP_NAME} listening on http://0.0.0.0:{port}")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
