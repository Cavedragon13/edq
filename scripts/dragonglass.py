#!/usr/bin/env python3
"""
DragonGlass — Street View Scout + AI Transform
Port 8040 | Google Maps Street View + Gemini image editing
"""

import os
import sys
import json
import asyncio
import base64
from pathlib import Path
from datetime import datetime
from io import BytesIO

import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from PIL import Image
from dotenv import load_dotenv
import google.genai as genai
from google.genai import types
import uvicorn

sys.path.insert(0, '/srv/containers/edq')
from scripts import provider_models

load_dotenv("/srv/containers/edq/.env")
GOOGLE_API_KEY = os.getenv("STREET_VIEW_API_KEY") or os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    print("❌ GOOGLE_API_KEY not found in /srv/containers/edq/.env")
    sys.exit(1)

_genai_client = genai.Client(api_key=GOOGLE_API_KEY)

def gemini_image_model():
    return provider_models.resolve_model('google', 'image_edit', modality='image').get('model') or 'gemini-3.1-flash-image-preview'

OUTPUT_DIR = Path.home() / "ai_generated" / "dragonglass"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

HTML_PATH = Path(__file__).parent.parent / "media" / "dragonglass.html"

STREETVIEW_URL = "https://maps.googleapis.com/maps/api/streetview"
METADATA_URL   = "https://maps.googleapis.com/maps/api/streetview/metadata"

app = FastAPI(title="DragonGlass")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def root():
    html = HTML_PATH.read_text()
    html = html.replace("__MAPS_API_KEY__", GOOGLE_API_KEY)
    return HTMLResponse(html)


class CaptureRequest(BaseModel):
    lat: float
    lng: float
    heading: float
    pitch: float
    fov: int = 90


@app.post("/api/capture")
async def capture(req: CaptureRequest):
    # Metadata check first (free)
    try:
        meta = requests.get(METADATA_URL, params={
            "location": f"{req.lat},{req.lng}",
            "key": GOOGLE_API_KEY,
            "source": "outdoor",
        }, timeout=10).json()
    except requests.RequestException as e:
        raise HTTPException(502, f"Network error: {e}")

    if meta.get("status") == "REQUEST_DENIED":
        raise HTTPException(403, "API key rejected — check Street View Static API is enabled")
    if meta.get("status") != "OK":
        raise HTTPException(404, f"No Street View imagery here (status: {meta.get('status')})")

    loc = meta["location"]
    params = {
        "size":            "640x640",
        "location":        f"{loc['lat']},{loc['lng']}",
        "heading":         round(req.heading, 1),
        "pitch":           round(req.pitch, 1),
        "fov":             max(10, min(120, req.fov)),
        "key":             GOOGLE_API_KEY,
        "source":          "outdoor",
        "return_error_code": "true",
    }
    try:
        resp = requests.get(STREETVIEW_URL, params=params, timeout=15)
    except requests.RequestException as e:
        raise HTTPException(502, f"Network error: {e}")

    if resp.status_code == 404:
        raise HTTPException(404, "No imagery at this exact spot")
    if resp.status_code != 200:
        raise HTTPException(resp.status_code, f"Street View API returned {resp.status_code}")

    img = Image.open(BytesIO(resp.content)).convert("RGB")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename  = f"sv_{timestamp}_h{int(req.heading)}_p{int(req.pitch)}.jpg"
    out_path  = OUTPUT_DIR / filename
    img.save(str(out_path), quality=92)

    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85)
    img_b64 = base64.b64encode(buf.getvalue()).decode()

    date_str = meta.get("date", "")
    pano_id  = meta.get("pano_id", "")[:10]
    info = (
        f"📍 {loc['lat']:.5f}, {loc['lng']:.5f}  ·  heading {req.heading:.0f}°  ·  "
        f"pitch {req.pitch:.0f}°  ·  fov {req.fov}°"
        + (f"  ·  {date_str}" if date_str else "")
        + (f"  ·  pano {pano_id}…" if pano_id else "")
        + f"\n💾 {out_path}"
    )

    return {"path": str(out_path), "filename": filename, "image_b64": img_b64, "info": info}


class TransformRequest(BaseModel):
    image_path: str
    prompt: str


@app.post("/api/transform")
async def transform(req: TransformRequest):
    async def generate():
        try:
            yield f"data: {json.dumps({'status': 'generating', 'message': '⏳ Sending to Gemini…'})}\n\n"

            img_path = Path(req.image_path)
            if not img_path.exists():
                yield f"data: {json.dumps({'status': 'error', 'message': f'Image not found: {img_path}'})}\n\n"
                return

            image_bytes = img_path.read_bytes()

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: _genai_client.models.generate_content(
                model=gemini_image_model(),
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                    req.prompt,
                ],
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE", "TEXT"],
                ),
            ))

            # Extract image part
            out_bytes = None
            for part in response.candidates[0].content.parts:
                if part.inline_data is not None:
                    out_bytes = part.inline_data.data
                    break

            if out_bytes is None:
                yield f"data: {json.dumps({'status': 'error', 'message': '❌ Gemini returned no image'})}\n\n"
                return

            out_img   = Image.open(BytesIO(out_bytes)).convert("RGB")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path  = OUTPUT_DIR / f"transformed_{timestamp}.jpg"
            out_img.save(str(out_path), quality=92)

            buf = BytesIO()
            out_img.save(buf, format="JPEG", quality=85)
            img_b64 = base64.b64encode(buf.getvalue()).decode()

            yield f"data: {json.dumps({'status': 'done', 'message': f'✅ Done  ·  {out_path}', 'image_b64': img_b64, 'path': str(out_path)})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'status': 'error', 'message': f'❌ {e}'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/api/status")
async def status():
    payload = provider_models.status_payload('DragonGlass', providers=['google'], default_provider='google')
    payload['output_dir'] = str(OUTPUT_DIR)
    payload['active_image_model'] = gemini_image_model()
    return payload


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8040, log_level="info")
