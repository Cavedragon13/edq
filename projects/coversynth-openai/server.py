#!/usr/bin/env python3
import cgi
import json
import os
import re
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
LOG_DIR = Path("/home/edq/ai_generated/coversynth-openai")
LOG_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv("/srv/containers/edq/.env")
load_dotenv(ROOT / ".env", override=False)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=120)
ANALYSIS_MODELS = ["gpt-5.4-mini", "gpt-5.4-nano", "gpt-5.2", "gpt-5", "gpt-4.1-mini"]


def status_payload():
    return provider_models.status_payload("CoverSynth OpenAI", providers=["openai"], default_provider="openai")


def analysis_models():
    return provider_models.models_for("openai", "text") or ANALYSIS_MODELS


def image_models():
    return provider_models.models_for("openai", "image") or ["gpt-image-2"]


def clean_json(text):
    match = re.search(r"\{.*\}", text or "", re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def looks_like_local_path(text):
    value = (text or "").strip().strip('"')
    if "\n" in value or len(value) > 600:
        return False
    pathish = value.startswith(("/", "~/")) or re.match(r"^[A-Za-z]:[\\/]", value)
    return bool(pathish and re.search(r"\.(pdf|txt|csv|md|rtf)$", value, re.I))


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


def log_event(kind, payload):
    record = {"ts": datetime.now(timezone.utc).isoformat(), "kind": kind, **payload}
    with (LOG_DIR / "coversynth-openai.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


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
        if length > 25 * 1024 * 1024:
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
            return self._json(404, {"error": "Unknown endpoint"})
        except Exception as exc:
            return self._json(500, provider_models.error_payload(exc))

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
        available_models = analysis_models()
        model = data.get("model") if data.get("model") in available_models else provider_models.resolve_model("openai", "analysis").get("model")
        if not playlist:
            return self._json(400, {"error": "Add playlist text or upload a PDF/text file first."})
        if looks_like_local_path(playlist):
            return self._json(400, {"error": "That looks like a file path, not file contents. Use the upload/drop area so the browser sends the PDF to udragon."})

        prompt = f"""Analyze this playlist or track list for cover art direction. Research from your built-in music knowledge only; do not invent certainty.

Return compact JSON with keys: title, summary, dominant_moods, sentiment, genres, visual_motifs, color_palette, avoid, cover_prompt, track_notes.

The cover_prompt must describe a square Apple Music style playlist cover, no text/logos, suitable for GPT Image 2.

Playlist:
{playlist[:24000]}"""
        response = client.responses.create(model=model, input=prompt)
        raw = getattr(response, "output_text", "") or ""
        analysis = clean_json(raw) or {"summary": raw, "cover_prompt": raw}
        log_event("analysis", {"model": model, "analysis": analysis})
        self._json(200, {"model": model, "analysis": analysis, "raw": raw})

    def generate(self, data):
        prompt = (data.get("prompt") or "").strip()
        refinement = (data.get("refinement") or "").strip()
        quality = data.get("quality") if data.get("quality") in {"low", "medium", "high"} else "medium"
        if refinement:
            prompt = f"{prompt}\n\nRefinement request: {refinement}\nKeep the same playlist-cover concept unless the refinement says otherwise."
        if not prompt:
            return self._json(400, {"error": "Image prompt is required"})
        image_model = data.get("model") if data.get("model") in image_models() else provider_models.resolve_model("openai", "image_generation").get("model")
        result = client.images.generate(
            model=image_model,
            prompt=prompt,
            size="1024x1024",
            quality=quality,
            output_format="png",
        )
        image_b64 = result.data[0].b64_json
        log_event("image", {"model": image_model, "quality": quality, "prompt": prompt})
        self._json(200, {"model": image_model, "image": image_b64, "prompt": prompt})


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8053"))
    print(f"CoverSynth OpenAI listening on http://0.0.0.0:{port}")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
