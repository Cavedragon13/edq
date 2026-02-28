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
from PIL import Image, ImageFilter
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
    post_process:     bool       = Form(False),
    alpha_threshold:  int        = Form(128),
    mask_expand:      int        = Form(0),
    feather:          int        = Form(0),
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

    # 1. Feather: blur the alpha mask for soft edges (before threshold)
    if feather > 0:
        r, g, b, alpha = result.split()
        alpha = alpha.filter(ImageFilter.GaussianBlur(radius=feather))
        result = Image.merge("RGBA", (r, g, b, alpha))

    # 2. Alpha threshold: remap alpha curve without binarizing
    # Shift the midpoint: low threshold keeps more (boosts alpha), high removes more (cuts alpha)
    # Uses a levels remap: new_alpha = clamp((alpha - threshold) / (255 - threshold) * 255, 0, 255)
    if alpha_threshold != 128:
        r, g, b, alpha = result.split()
        t = alpha_threshold
        if t < 128:
            # Keep more: boost low-alpha pixels up
            alpha = alpha.point(lambda x: min(255, int(x * 255 / max(t, 1))))
        else:
            # Remove more: slide the ramp so only high-confidence pixels survive
            alpha = alpha.point(lambda x: max(0, min(255, int((x - t) * 255 / max(255 - t, 1)))))
        result = Image.merge("RGBA", (r, g, b, alpha))

    # 3. Mask edge expand/shrink (negative = erode, positive = dilate)
    if mask_expand != 0:
        r, g, b, alpha = result.split()
        kernel_size = 2 * abs(mask_expand) + 1
        if mask_expand > 0:
            alpha = alpha.filter(ImageFilter.MaxFilter(kernel_size))
        else:
            alpha = alpha.filter(ImageFilter.MinFilter(kernel_size))
        result = Image.merge("RGBA", (r, g, b, alpha))

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
