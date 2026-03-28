#!/usr/bin/env python3
"""
Real-ESRGAN Upscaler - Native UI Server
Port: 8010

API:
  GET  /            → serves realesrgan.html
  POST /api/upscale → multipart: file, model, output_scale, face_enhance,
                                 tile_size, denoise_strength
                    → returns PNG binary + X-Dimensions header
"""

import io
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import torch
import uvicorn
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, Response
from PIL import Image

OUTPUT_DIR = Path.home() / "ai_generated" / "realesrgan"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
MEDIA_DIR = Path("/srv/containers/edq/media")

device = "cuda" if torch.cuda.is_available() else "cpu"

MODELS = {
    "RealESRGAN_x4plus": {
        "label": "RealESRGAN x4+ — General",
        "scale": 4,
    },
    "RealESRGAN_x4plus_anime_6B": {
        "label": "RealESRGAN x4+ Anime",
        "scale": 4,
    },
    "RealESRGAN_x2plus": {
        "label": "RealESRGAN x2+",
        "scale": 2,
    },
    "realesr-general-x4v3": {
        "label": "Real-ESRGAN General v3",
        "scale": 4,
    },
}

MODEL_URLS = {
    "RealESRGAN_x4plus":           "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
    "RealESRGAN_x4plus_anime_6B":  "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth",
    "RealESRGAN_x2plus":           "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth",
    "realesr-general-x4v3":        "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth",
}

upsampler     = None
current_model = None
face_enhancer = None


def load_model(model_name: str):
    global upsampler, current_model
    if current_model == model_name and upsampler is not None:
        return
    if upsampler is not None:
        del upsampler
        torch.cuda.empty_cache()

    from basicsr.archs.rrdbnet_arch import RRDBNet
    from realesrgan import RealESRGANer

    if model_name == "RealESRGAN_x4plus":
        model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
        netscale = 4
    elif model_name == "RealESRGAN_x4plus_anime_6B":
        model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=6, num_grow_ch=32, scale=4)
        netscale = 4
    elif model_name == "RealESRGAN_x2plus":
        model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=2)
        netscale = 2
    elif model_name == "realesr-general-x4v3":
        from realesrgan.archs.srvgg_arch import SRVGGNetCompact
        model = SRVGGNetCompact(num_in_ch=3, num_out_ch=3, num_feat=64, num_conv=32, upscale=4, act_type='prelu')
        netscale = 4
    else:
        raise ValueError(f"Unknown model: {model_name}")

    upsampler = RealESRGANer(
        scale=netscale,
        model_path=MODEL_URLS[model_name],
        model=model,
        tile=0,
        tile_pad=10,
        pre_pad=0,
        half=(device == "cuda"),
        gpu_id=0 if device == "cuda" else None,
    )
    current_model = model_name


def load_face_enhancer():
    global face_enhancer
    if face_enhancer is not None:
        return
    from gfpgan import GFPGANer
    face_enhancer = GFPGANer(
        model_path='https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.3.pth',
        upscale=1, arch='clean', channel_multiplier=2, bg_upsampler=upsampler
    )


def pil_to_bgr(image: Image.Image) -> np.ndarray:
    arr = np.array(image)
    if len(arr.shape) == 2:
        return cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
    if arr.shape[2] == 4:
        return cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


app = FastAPI(title="Real-ESRGAN")


@app.get("/")
async def serve_ui():
    return FileResponse(MEDIA_DIR / "realesrgan.html")


@app.post("/api/upscale")
async def api_upscale(
    file:             UploadFile = File(...),
    model:            str        = Form("RealESRGAN_x4plus"),
    output_scale:     float      = Form(4.0),
    face_enhance:     bool       = Form(False),
    tile_size:        int        = Form(0),
    denoise_strength: float      = Form(0.5),
):
    raw = await file.read()
    img = Image.open(io.BytesIO(raw))
    in_w, in_h = img.width, img.height

    load_model(model)
    upsampler.tile = tile_size
    img_bgr = pil_to_bgr(img)

    if face_enhance:
        load_face_enhancer()
        _, _, output_bgr = face_enhancer.enhance(
            img_bgr, has_aligned=False, only_center_face=False,
            paste_back=True, weight=0.5
        )
    else:
        output_bgr, _ = upsampler.enhance(img_bgr, outscale=output_scale)

    output_rgb = cv2.cvtColor(output_bgr, cv2.COLOR_BGR2RGB)
    output_pil = Image.fromarray(output_rgb)
    out_w, out_h = output_pil.width, output_pil.height

    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"upscaled_{ts}_{in_w}x{in_h}_to_{out_w}x{out_h}.png"
    path     = OUTPUT_DIR / filename
    output_pil.save(path, "PNG")

    buf = io.BytesIO()
    output_pil.save(buf, "PNG")
    return Response(
        content=buf.getvalue(),
        media_type="image/png",
        headers={
            "X-Input-Size":  f"{in_w}×{in_h}",
            "X-Output-Size": f"{out_w}×{out_h}",
            "X-Saved-Path":  str(path),
        }
    )


if __name__ == "__main__":
    port = 8010
    print(f"🐉 Real-ESRGAN (native UI) → http://0.0.0.0:{port}  [{device.upper()}]")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
