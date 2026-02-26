#!/usr/bin/env python3
"""
Rembg Background Remover - Native UI Server
Port: 8112 (dev) → 8012 (production after approval)

API:
  GET  /          → serves rembg.html
  POST /api/remove → multipart: file, model, alpha_matting, fg_threshold,
                                bg_threshold, post_process
                   → returns PNG binary
"""

import io
from datetime import datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, Response
from PIL import Image
from rembg import new_session, remove

OUTPUT_DIR = Path.home() / "ai_generated" / "rembg"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MEDIA_DIR = Path("/srv/containers/edq/media")

MODELS = {
    "isnet-general-use": "isnet-general-use",
    "u2net":             "u2net",
    "u2net_human_seg":   "u2net_human_seg",
    "isnet-anime":       "isnet-anime",
    "silueta":           "silueta",
    "u2netp":            "u2netp",
}

_sessions: dict = {}

def get_session(model_name: str):
    if model_name not in _sessions:
        print(f"Loading model: {model_name}")
        _sessions[model_name] = new_session(model_name)
    return _sessions[model_name]

app = FastAPI(title="Rembg")

@app.get("/")
async def serve_ui():
    return FileResponse(MEDIA_DIR / "rembg.html")

@app.post("/api/remove")
async def api_remove(
    file:            UploadFile = File(...),
    model:           str        = Form("isnet-general-use"),
    alpha_matting:   bool       = Form(False),
    fg_threshold:    int        = Form(240),
    bg_threshold:    int        = Form(10),
    post_process:    bool       = Form(False),
):
    raw = await file.read()
    img = Image.open(io.BytesIO(raw)).convert("RGBA")

    model_key = model if model in MODELS else "isnet-general-use"
    session   = get_session(MODELS[model_key])

    result = remove(
        img,
        session=session,
        alpha_matting=alpha_matting,
        alpha_matting_foreground_threshold=fg_threshold,
        alpha_matting_background_threshold=bg_threshold,
        post_process_mask=post_process,
    )

    # Save to disk
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUTPUT_DIR / f"rembg_{ts}.png"
    result.save(path, "PNG")

    # Return PNG bytes
    buf = io.BytesIO()
    result.save(buf, "PNG")
    return Response(content=buf.getvalue(), media_type="image/png",
                    headers={"X-Saved-Path": str(path)})

if __name__ == "__main__":
    port = 8012
    print(f"🐉 Rembg (native UI) → http://0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
