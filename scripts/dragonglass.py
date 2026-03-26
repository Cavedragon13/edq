#!/usr/bin/env python3
"""
DragonGlass — Street View Scout + AI Transform
Port 8040 | Google Maps Street View + FLUX.1-schnell (local, Apache 2.0)
"""

import os
import sys
import json
import asyncio
import base64
import random as _random
from pathlib import Path
from datetime import datetime
from io import BytesIO
from typing import Optional

import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from PIL import Image
from dotenv import load_dotenv
import uvicorn

load_dotenv("/srv/containers/edq/.env")
GOOGLE_API_KEY = os.getenv("STREET_VIEW_API_KEY") or os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    print("❌ GOOGLE_API_KEY not found in /srv/containers/edq/.env")
    sys.exit(1)

MODEL_PATH = "/srv/containers/edq/models/flux1-schnell"
if not Path(MODEL_PATH).joinpath("model_index.json").exists():
    print(f"❌ FLUX.1-schnell not found at {MODEL_PATH}")
    print("   Run: bash scripts/download_flux1_schnell.sh")
    sys.exit(1)

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

_pipe = None


def get_pipeline():
    global _pipe
    if _pipe is None:
        import torch
        from diffusers import FluxImg2ImgPipeline
        print("⏳ Loading FLUX.1-schnell pipeline…")
        _pipe = FluxImg2ImgPipeline.from_pretrained(
            MODEL_PATH,
            torch_dtype=torch.bfloat16,
            local_files_only=True,
        )
        _pipe.enable_sequential_cpu_offload()
        if hasattr(_pipe, "vae"):
            _pipe.vae.enable_slicing()
            _pipe.vae.enable_tiling()
        print("✅ Pipeline ready")
    return _pipe


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
    strength: float = 0.90
    steps: int = 8
    seed: int = 42
    randomize: bool = False


@app.post("/api/transform")
async def transform(req: TransformRequest):
    async def generate():
        try:
            yield f"data: {json.dumps({'status': 'loading', 'message': '⏳ Loading pipeline…'})}\n\n"

            loop = asyncio.get_event_loop()
            pipe = await loop.run_in_executor(None, get_pipeline)

            img_path = Path(req.image_path)
            if not img_path.exists():
                yield f"data: {json.dumps({'status': 'error', 'message': f'Image not found: {img_path}'})}\n\n"
                return

            input_img = Image.open(img_path).convert("RGB")
            actual_seed = _random.randint(0, 2**32 - 1) if req.randomize else req.seed

            yield f"data: {json.dumps({'status': 'generating', 'message': f'⏳ Generating — seed {actual_seed}…'})}\n\n"

            import torch
            generator = torch.Generator().manual_seed(actual_seed)

            result = await loop.run_in_executor(None, lambda: pipe(
                prompt=req.prompt,
                image=input_img,
                strength=req.strength,
                num_inference_steps=req.steps,
                guidance_scale=0.0,
                generator=generator,
            ))

            out_img   = result.images[0]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path  = OUTPUT_DIR / f"transformed_{timestamp}_s{actual_seed}.jpg"
            out_img.save(str(out_path), quality=92)

            buf = BytesIO()
            out_img.save(buf, format="JPEG", quality=85)
            img_b64 = base64.b64encode(buf.getvalue()).decode()

            yield f"data: {json.dumps({'status': 'done', 'message': f'✅ Done  ·  seed {actual_seed}  ·  {out_path}', 'image_b64': img_b64, 'path': str(out_path)})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'status': 'error', 'message': f'❌ {e}'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/api/status")
async def status():
    return {"pipeline_loaded": _pipe is not None, "output_dir": str(OUTPUT_DIR)}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8040, log_level="info")
