#!/usr/bin/env python3
"""Supra2-IMG Dragonsuite web service."""

import os
import sys

sys.path.insert(0, os.environ.get("DRAGONSUITE_SCRIPTS", "/srv/containers/edq/scripts"))
import gpu_runtime  # noqa: F401  (must load before any torch child process)

import datetime as dt
import re
import subprocess
import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

ROOT = Path("/srv/containers/edq")
APP_DIR = ROOT / "projects/Supra2-IMG"
VENV_PYTHON = ROOT / "venv_supra2_img/bin/python"
CHECKPOINT = ROOT / "models/supra2-img/model_final_ema.pt"
T5_DIR = ROOT / "models/supra2-img/flan-t5-base"
VAE_DIR = ROOT / "models/supra2-img/sd-vae-ft-mse"
OUT_ROOT = Path("/home/edq/ai_generated/supra2-img")
HTML = ROOT / "media/supra2_img.html"
PORT = 8070

OUT_ROOT.mkdir(parents=True, exist_ok=True)
GPU_LOCK = threading.Lock()
app = FastAPI(title="Supra2-IMG")


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=1200)
    seed: int = Field(default=0, ge=0, le=2**31 - 1)
    cfg: float = Field(default=3.0, ge=1.0, le=10.0)
    steps: int = Field(default=50, ge=1, le=100)


def slug(value: str) -> str:
    clean = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return clean[:42] or "image"


def output_name(prompt: str) -> str:
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"supra2_{stamp}_{uuid.uuid4().hex[:6]}_{slug(prompt)}.png"


@app.get("/")
def index():
    return FileResponse(HTML)


@app.get("/health")
def health():
    ready = all(path.exists() for path in (CHECKPOINT, T5_DIR / "config.json", VAE_DIR / "config.json"))
    return {"ok": ready, "service": "supra2-img", "models_ready": ready}


@app.get("/outputs/{name}")
def output(name: str):
    path = (OUT_ROOT / name).resolve()
    if path.parent != OUT_ROOT.resolve() or not path.is_file():
        raise HTTPException(404, "output not found")
    return FileResponse(path, media_type="image/png")


@app.post("/api/generate")
def generate(req: GenerateRequest):
    if not GPU_LOCK.acquire(blocking=False):
        raise HTTPException(409, "Another Supra2-IMG generation is already running.")
    name = output_name(req.prompt)
    path = OUT_ROOT / name
    env = os.environ.copy()
    env.update({
        "DRAGONSUITE_SCRIPTS": str(ROOT / "scripts"),
        "SUPRA2_CHECKPOINT": str(CHECKPOINT),
        "SUPRA2_T5_NAME": str(T5_DIR),
        "SUPRA2_VAE_NAME": str(VAE_DIR),
        "PYTHONUNBUFFERED": "1",
    })
    cmd = [
        str(VENV_PYTHON), str(APP_DIR / "inference.py"),
        "--prompt", req.prompt, "--seed", str(req.seed),
        "--cfg", str(req.cfg), "--steps", str(req.steps),
        "--n", "1", "--out", str(path),
    ]
    try:
        result = subprocess.run(
            cmd, cwd=APP_DIR, env=env, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=1800, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(504, "Supra2-IMG timed out after 30 minutes.") from exc
    finally:
        GPU_LOCK.release()
    if result.returncode != 0 or not path.is_file():
        tail = (result.stdout or "")[-1800:]
        raise HTTPException(500, f"Generation failed.\n{tail}")
    return {"ok": True, "filename": name, "url": f"/outputs/{name}", "log": result.stdout[-1200:]}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PORT)
