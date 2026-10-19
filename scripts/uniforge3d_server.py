#!/usr/bin/env python3
"""UniForge3D Studio — Dragonsuite service (port 8075).

Sparse, unposed multi-view images of ONE object -> textured GLB, using the
upstream UniForge3DImageTo3DPipeline (xibushu/UniForge3D, built on TRELLIS.2 + VGGT).
Upstream ships only a batch CLI (infer.py); this is a thin FastAPI wrapper around
the same pipeline call.

Outputs: ~/ai_generated/uniforge3d/<YYYY-MM-DD_HHMMSS>_<name>/
  views/NN.<ext>  prediction.glb  params.json     (+ ../latest.json)

Licence notes: UniForge3D code is MIT, but its VGGT-derived checkpoints are CC BY-NC 4.0
and the default background remover (BRIA RMBG-2.0) needs a separate commercial licence.
Personal / non-commercial use only.
"""
import datetime
import json
import os
import re
import sys
import threading
import time
import uuid
from pathlib import Path

ROOT = Path("/srv/containers/edq")
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "projects/UniForge3D"))
os.environ.setdefault("HF_HUB_OFFLINE", "1")   # models are pre-downloaded; never fetch at runtime

import gpu_runtime  # noqa: E402  (must precede torch: configures the CUDA allocator)
import torch  # noqa: E402
import uvicorn  # noqa: E402
from fastapi import FastAPI, File, Form, HTTPException, UploadFile  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from starlette.concurrency import run_in_threadpool  # noqa: E402

MODEL_DIR = ROOT / "models/uniforge3d"
OUT_ROOT = Path.home() / "ai_generated/uniforge3d"
HTML = ROOT / "media/uniforge3d.html"
PORT = 8075
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
MIN_VIEWS, MAX_VIEWS = 1, 8

OUT_ROOT.mkdir(parents=True, exist_ok=True)
app = FastAPI(title="UniForge3D Studio")
app.mount("/files", StaticFiles(directory=OUT_ROOT), name="files")

_lock = threading.Lock()          # one generation at a time (single GPU)
_pipeline = None
_pipeline_low_vram = None
PROGRESS = {"stage": "idle", "started": 0.0, "message": ""}


def _slug(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", name.strip()).strip("-")
    return s[:48] or "object"


def _get_pipeline(low_vram: bool):
    global _pipeline, _pipeline_low_vram
    if _pipeline is not None and _pipeline_low_vram == low_vram:
        return _pipeline
    _unload()
    from uniforge3d import UniForge3DImageTo3DPipeline
    _pipeline = UniForge3DImageTo3DPipeline.from_pretrained(
        MODEL_DIR, low_vram=low_vram, local_files_only=True)
    _pipeline_low_vram = low_vram
    return _pipeline


def _unload():
    global _pipeline, _pipeline_low_vram
    _pipeline = None
    _pipeline_low_vram = None
    import gc
    gc.collect()
    gpu_runtime.free_cuda_cache()


@app.get("/")
def index():
    return FileResponse(HTML)


@app.get("/api/status")
def status():
    return {
        "models_ready": (MODEL_DIR / "pipeline.json").is_file(),
        "loaded": _pipeline is not None,
        "busy": _lock.locked(),
        "cuda": torch.cuda.is_available(),
        "progress": PROGRESS | {"elapsed": round(time.time() - PROGRESS["started"], 1) if PROGRESS["started"] and PROGRESS["stage"] not in ("idle", "done", "error") else 0},
    }


@app.post("/api/unload")
def unload():
    if _lock.locked():
        raise HTTPException(409, "A generation is running.")
    _unload()
    return {"loaded": False}


@app.post("/api/generate")
async def generate(files: list[UploadFile] = File(...), name: str = Form(""),
                   seed: int = Form(-1), low_vram: bool = Form(True)):
    if not (MIN_VIEWS <= len(files) <= MAX_VIEWS):
        raise HTTPException(400, f"Upload {MIN_VIEWS}-{MAX_VIEWS} views of one object.")
    for f in files:
        if Path(f.filename or "").suffix.lower() not in IMAGE_SUFFIXES:
            raise HTTPException(400, f"Unsupported file: {f.filename}")
    if not (MODEL_DIR / "pipeline.json").is_file():
        raise HTTPException(503, "Models not downloaded — run scripts/download_uniforge3d_models.sh")
    if not _lock.acquire(blocking=False):
        raise HTTPException(409, "Another generation is running.")
    try:
        stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
        folder = OUT_ROOT / f"{stamp}_{_slug(name or Path(files[0].filename).stem)}"
        (folder / "views").mkdir(parents=True)
        view_paths = []
        for i, f in enumerate(files, 1):
            p = folder / "views" / f"{i:03d}{Path(f.filename).suffix.lower()}"
            p.write_bytes(await f.read())
            view_paths.append(p)
        if seed < 0:
            seed = uuid.uuid4().int % (2**31)

        PROGRESS.update(stage="loading", started=time.time(), message="Loading models (first run is slow)")
        out = folder / "prediction.glb"
        t0 = time.time()
        def work():
            pipe = _get_pipeline(low_vram)
            PROGRESS.update(stage="running", message=f"{len(view_paths)} views, seed {seed}")
            with gpu_runtime.oom_guard("UniForge3D generation"):
                pipe.run(view_paths, out, seed=seed)

        try:
            await run_in_threadpool(work)      # keep the event loop free for /api/status polls
        except RuntimeError as exc:          # includes the clean OOM message from oom_guard
            _unload()
            PROGRESS.update(stage="error", message=str(exc))
            return JSONResponse(status_code=507, content={"error": str(exc)})
        except Exception as exc:
            PROGRESS.update(stage="error", message=f"{type(exc).__name__}: {exc}")
            raise HTTPException(500, f"{type(exc).__name__}: {exc}")
        secs = round(time.time() - t0, 1)
        params = {"name": folder.name, "views": len(view_paths), "seed": seed, "low_vram": low_vram,
                  "seconds": secs, "created": datetime.datetime.now().isoformat(timespec="seconds"),
                  "glb_bytes": out.stat().st_size}
        (folder / "params.json").write_text(json.dumps(params, indent=2))
        (OUT_ROOT / "latest.json").write_text(json.dumps({"folder": folder.name, **params}, indent=2))
        PROGRESS.update(stage="done", message=f"{secs}s")
        return {"folder": folder.name, "seconds": secs, "glb": f"/files/{folder.name}/prediction.glb"}
    finally:
        _lock.release()


@app.get("/api/gallery")
def gallery():
    items = []
    for d in sorted((p for p in OUT_ROOT.iterdir() if p.is_dir()), reverse=True)[:40]:
        if (d / "prediction.glb").is_file():
            views = sorted((d / "views").glob("*")) if (d / "views").is_dir() else []
            items.append({"folder": d.name, "glb": f"/files/{d.name}/prediction.glb",
                          "thumb": f"/files/{d.name}/views/{views[0].name}" if views else None})
    return items


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
