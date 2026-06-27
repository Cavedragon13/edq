#!/usr/bin/env python3
"""RPG Char Gen local server.

Serves the static app and proxies OpenAI image generation so OPENAI_API_KEY stays
in .env instead of being exposed to the browser.
"""

from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_DIR = Path(__file__).resolve().parent
ENV_PATHS = (
    Path("/srv/containers/edq/.env"),
    BASE_DIR / ".env",
)
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8034"))
OPENAI_IMAGES_API_URL = "https://api.openai.com/v1/images/generations"


def load_env() -> None:
  for env_path in ENV_PATHS:
    if not env_path.exists():
      continue

    for line in env_path.read_text(encoding="utf-8").splitlines():
      stripped = line.strip()
      if not stripped or stripped.startswith("#") or "=" not in stripped:
        continue

      key, value = stripped.split("=", 1)
      key = key.strip()
      value = value.strip().strip('"').strip("'")
      os.environ.setdefault(key, value)


class Handler(SimpleHTTPRequestHandler):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, directory=str(BASE_DIR), **kwargs)

  def do_POST(self) -> None:
    if self.path == "/api/generate-portrait":
      self.generate_portrait()
      return

    self.send_error(HTTPStatus.NOT_FOUND, "Not found")

  def generate_portrait(self) -> None:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
      self.send_json(
        {"error": "OPENAI_API_KEY is not set in /srv/containers/edq/.env or project .env."},
        HTTPStatus.SERVICE_UNAVAILABLE,
      )
      return

    try:
      content_length = int(self.headers.get("Content-Length", "0"))
    except ValueError:
      self.send_json({"error": "Invalid Content-Length."}, HTTPStatus.BAD_REQUEST)
      return

    if content_length <= 0 or content_length > 64 * 1024:
      self.send_json({"error": "Request body must be between 1 byte and 64KB."}, HTTPStatus.BAD_REQUEST)
      return

    try:
      payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
      self.send_json({"error": "Request body must be valid JSON."}, HTTPStatus.BAD_REQUEST)
      return

    prompt = str(payload.get("prompt", "")).strip()
    if not prompt:
      self.send_json({"error": "prompt is required."}, HTTPStatus.BAD_REQUEST)
      return

    size = str(payload.get("size") or "1024x1536")

    # gpt-image-2 has minimum pixel budget (~1MP); validate
    try:
      w, h = map(int, size.split('x'))
      if w * h < 1000000:  # ~1MP minimum
        self.send_json({
          "error": f"Size too small for gpt-image-2. Minimum ~1MP (1024x1024). Got {w}x{h}={w*h:,} pixels"
        }, HTTPStatus.BAD_REQUEST)
        return
    except (ValueError, AttributeError):
      self.send_json({"error": f"Invalid size format: {size}. Use WIDTHxHEIGHT"}, HTTPStatus.BAD_REQUEST)
      return

    openai_payload = {
      "model": str(payload.get("model") or "gpt-image-2"),
      "prompt": prompt,
      "size": size,
      "quality": str(payload.get("quality") or "medium"),
    }

    request = Request(
      OPENAI_IMAGES_API_URL,
      data=json.dumps(openai_payload).encode("utf-8"),
      headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
      },
      method="POST",
    )

    try:
      with urlopen(request, timeout=120) as response:
        openai_response = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
      message = self.extract_openai_error(error)
      self.send_json({"error": message}, error.code)
      return
    except (URLError, TimeoutError) as error:
      self.send_json({"error": f"OpenAI request failed: {error}"}, HTTPStatus.BAD_GATEWAY)
      return
    except json.JSONDecodeError:
      self.send_json({"error": "OpenAI returned invalid JSON."}, HTTPStatus.BAD_GATEWAY)
      return

    image = (openai_response.get("data") or [{}])[0].get("b64_json")
    if not image:
      self.send_json({"error": "OpenAI did not return image data."}, HTTPStatus.BAD_GATEWAY)
      return

    self.send_json({"image": f"data:image/png;base64,{image}", "model": openai_payload["model"]})

  def extract_openai_error(self, error: HTTPError) -> str:
    try:
      payload = json.loads(error.read().decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
      return f"OpenAI returned HTTP {error.code}."

    return payload.get("error", {}).get("message") or f"OpenAI returned HTTP {error.code}."

  def send_json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
    response = json.dumps(payload).encode("utf-8")
    self.send_response(status)
    self.send_header("Content-Type", "application/json")
    self.send_header("Content-Length", str(len(response)))
    self.end_headers()
    self.wfile.write(response)


def main() -> None:
  load_env()
  server = ThreadingHTTPServer((HOST, PORT), Handler)
  print(f"RPG Char Gen ready at http://{HOST}:{PORT}")
  print(f"OPENAI_API_KEY: {'loaded' if os.environ.get('OPENAI_API_KEY') else 'missing'}")
  try:
    server.serve_forever()
  except KeyboardInterrupt:
    print("\nRPG Char Gen server stopped")


if __name__ == "__main__":
  main()
