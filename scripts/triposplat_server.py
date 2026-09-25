#!/usr/bin/env python3
"""TripoSplat Studio — Dragonsuite service (port 8067).

Image -> 3D Gaussian splat with a human checkpoint before the GPU run:
  1. upload      -> BiRefNet cutout (skipped if the upload already has alpha)
  2. mask edit   -> browser brushes keep/erase on the alpha matte
  3. preview     -> the exact 1024x1024 composite the encoders will see
  4. approve     -> generate; everything saved in one readable folder
  5. optional    -> headless Blender mesh (scripts/splat_to_blender.py)

Outputs: ~/ai_generated/triposplat/<YYYY-MM-DD_HHMMSS>_<name>/
  input.png  mask.png  prepared.png  splat.ply  [splat.splat]  preview.png  params.json
  (+ mesh.blend, mesh_front.png, mesh_34.png after the Blender step)
"""
import gpu_runtime  # noqa: F401  (FIRST — configures the CUDA allocator before torch import)

import base64
import datetime
import io
import json
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

import numpy as np
import torch
import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps
from pydantic import BaseModel, Field

ROOT = Path("/srv/containers/edq")
APP_DIR = ROOT / "projects/TripoSplat"
CKPT = ROOT / "models/triposplat"
OUT_ROOT = Path.home() / "ai_generated/triposplat"
HTML = ROOT / "media/triposplat.html"
PORT = 8067

sys.path.insert(0, str(APP_DIR))
sys.path.insert(0, str(ROOT / "scripts"))
from triposplat import TripoSplatPipeline, _CANVAS_SIZE  # noqa: E402
import triposplat_catalog as catalog  # noqa: E402

OUT_ROOT.mkdir(parents=True, exist_ok=True)

print("[triposplat] loading pipeline...", flush=True)
PIPE = TripoSplatPipeline(
    ckpt_path=str(CKPT / "diffusion_models/triposplat_fp16.safetensors"),
    decoder_path=str(CKPT / "vae/triposplat_vae_decoder_fp16.safetensors"),
    dinov3_path=str(CKPT / "clip_vision/dino_v3_vit_h.safetensors"),
    flux2_vae_encoder_path=str(CKPT / "vae/flux2-vae.safetensors"),
    rmbg_path=str(CKPT / "background_removal/birefnet.safetensors"),
    device="cuda",
)
print("[triposplat] pipeline ready", flush=True)

GPU_LOCK = threading.Lock()
SESSIONS: dict[str, dict] = {}   # upload id -> images kept between steps
PROGRESS: dict[str, dict] = {}   # upload id -> {"stage", "step", "total"}
MAX_SESSIONS = 16

app = FastAPI(title="TripoSplat Studio")


# ---------------------------------------------------------------- helpers

def _png_data_url(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _decode_data_url(data_url: str) -> Image.Image:
    try:
        payload = data_url.split(",", 1)[1]
        return Image.open(io.BytesIO(base64.b64decode(payload)))
    except Exception as exc:
        raise HTTPException(400, f"bad image data: {exc}")


def _session(sid: str) -> dict:
    s = SESSIONS.get(sid)
    if s is None:
        raise HTTPException(404, "Upload expired — please load the image again.")
    return s


def _prune_sessions():
    while len(SESSIONS) > MAX_SESSIONS:
        oldest = min(SESSIONS, key=lambda k: SESSIONS[k]["created"])
        SESSIONS.pop(oldest, None)
        PROGRESS.pop(oldest, None)


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s[:40] or "splat"


def _folder(name: str) -> Path:
    base = OUT_ROOT / f"{datetime.datetime.now():%Y-%m-%d_%H%M%S}_{_slug(name)}"
    path, n = base, 2
    while path.exists():
        path = base.with_name(f"{base.name}-{n}")
        n += 1
    path.mkdir(parents=True)
    return path


def _safe_folder(folder: str) -> Path:
    path = (OUT_ROOT / folder).resolve()
    if path.parent != OUT_ROOT.resolve() or not (path / "splat.ply").exists():
        raise HTTPException(404, "no such splat folder")
    return path


def _gpu(label: str, fn):
    """Serialize GPU work and turn an OOM into a clean HTTP 507."""
    with GPU_LOCK:
        try:
            with gpu_runtime.oom_guard(label):
                return fn()
        except RuntimeError as exc:
            raise HTTPException(507, str(exc))


# ---------------------------------------------------------------- routes

@app.get("/")
def index():
    return FileResponse(HTML)


@app.post("/api/cutout")
async def cutout(file: UploadFile = File(...)):
    """Step 1: load the image at the pipeline's working scale and matte it."""
    raw = await file.read()
    try:
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(raw)))
    except Exception as exc:
        raise HTTPException(400, f"could not read image: {exc}")
    img = img.convert("RGBA")
    w, h = img.size
    s = _CANVAS_SIZE / min(w, h)  # same scaling as upstream preprocess_image
    img = img.resize((max(1, round(w * s)), max(1, round(h * s))), Image.LANCZOS)

    alpha = img.getchannel("A")
    had_alpha = np.asarray(alpha).min() < 255
    if not had_alpha:
        matted = _gpu("background removal", lambda: PIPE.rmbg.remove_background(img.convert("RGB")))
        alpha = matted.getchannel("A")

    sid = uuid.uuid4().hex[:12]
    SESSIONS[sid] = {
        "created": time.time(),
        "name": Path(file.filename or "splat").stem,
        "input": img.copy(),           # upload at working scale, incl. original alpha
        "rgb": img.convert("RGB"),
        "auto_alpha": alpha,
    }
    _prune_sessions()
    return {
        "id": sid,
        "name": SESSIONS[sid]["name"],
        "width": img.width,
        "height": img.height,
        "had_alpha": bool(had_alpha),
        "image": _png_data_url(img.convert("RGB")),
        "mask": _png_data_url(alpha),
    }


class PrepareReq(BaseModel):
    id: str
    mask: str                       # PNG data URL, white = keep
    erode: int = Field(1, ge=0, le=8)


@app.post("/api/prepare")
def prepare(req: PrepareReq):
    """Step 2-3: apply the edited mask and return the exact model input."""
    s = _session(req.id)
    mask = _decode_data_url(req.mask).convert("L")
    if mask.size != s["rgb"].size:
        mask = mask.resize(s["rgb"].size, Image.BILINEAR)
    m = np.asarray(mask).copy()
    if m.max() == 0:
        raise HTTPException(400, "The mask is empty — paint back the subject first.")
    # Upstream re-runs background removal when alpha is fully opaque; a single
    # 254 pixel keeps the user's "keep everything" mask authoritative.
    if m.min() == 255:
        m[0, 0] = 254
    mask = Image.fromarray(m, "L")
    rgba = s["rgb"].copy()
    rgba.putalpha(mask)
    prepared = PIPE.preprocess_image(rgba, erode_radius=req.erode)  # no GPU: alpha is real
    s.update(mask=mask, prepared=prepared, erode=req.erode)
    return {"prepared": _png_data_url(prepared)}


class GenerateReq(BaseModel):
    id: str
    name: str = ""
    seed: int = 42
    steps: int = Field(20, ge=1, le=50)
    guidance: float = Field(3.0, ge=1.0, le=10.0)
    shift: float = Field(3.0, ge=1.0, le=10.0)
    num_gaussians: int = Field(262144, ge=32768, le=262144)
    save_splat: bool = False


@app.post("/api/generate")
def generate(req: GenerateReq):
    """Step 4: approved — run the GPU pipeline and save everything together."""
    s = _session(req.id)
    if "prepared" not in s:
        raise HTTPException(400, "Preview the model input first, then approve.")
    prog = PROGRESS[req.id] = {"stage": "encoding", "step": 0, "total": req.steps}

    def cb(step, total):
        prog.update(stage="sampling", step=step, total=total)

    def run():
        t0 = time.time()
        gen = torch.Generator(device=PIPE._device).manual_seed(int(req.seed))
        cond = PIPE.encode_image(s["prepared"], generator=gen)
        out = PIPE.sample_latent(cond, steps=req.steps, guidance_scale=req.guidance,
                                 shift=req.shift, generator=gen, callback=cb)
        prog.update(stage="decoding")
        g = PIPE.decode_latent(out["latent"], num_gaussians=req.num_gaussians)
        return g, time.time() - t0

    with torch.no_grad():
        gaussian, secs = _gpu("splat generation", run)

    prog.update(stage="saving")
    name = req.name.strip() or s["name"]
    folder = _folder(name)
    s["input"].save(folder / "input.png")
    s["mask"].save(folder / "mask.png")
    s["prepared"].save(folder / "prepared.png")
    gaussian.save_ply(str(folder / "splat.ply"))
    if req.save_splat:
        gaussian.save_splat(str(folder / "splat.splat"))
    catalog.write_preview(folder / "splat.ply")
    params = req.model_dump(exclude={"id"}) | {
        "name": name,
        "erode": s.get("erode", 1),
        "gaussians": int(gaussian.get_xyz.shape[0]),
        "seconds": round(secs, 1),
        "created": datetime.datetime.now().isoformat(timespec="seconds"),
        "model": "VAST-AI/TripoSplat",
        "code_rev": _git_rev(),
    }
    (folder / "params.json").write_text(json.dumps(params, indent=2))
    (OUT_ROOT / "latest.json").write_text(json.dumps({"folder": folder.name, **params}, indent=2))
    prog.update(stage="done")
    return {"folder": folder.name, "seconds": round(secs, 1), "gaussians": params["gaussians"]}


@app.get("/api/progress/{sid}")
def progress(sid: str):
    return PROGRESS.get(sid, {"stage": "idle", "step": 0, "total": 0})


BLENDER_JOBS: dict[str, dict] = {}


def _blender_bin() -> str:
    exe = shutil.which("blender") or "/snap/bin/blender"
    if not Path(exe).exists():
        raise HTTPException(500, "Blender not found (expected on PATH or /snap/bin/blender)")
    return exe


def _run_blender(folder: Path):
    job = BLENDER_JOBS[folder.name]
    log = folder / "blender.log"
    try:
        with open(log, "w") as fh:
            rc = subprocess.run(
                [_blender_bin(), "-b", "--python", str(ROOT / "scripts/splat_to_blender.py"), "--", str(folder)],
                stdout=fh, stderr=subprocess.STDOUT, timeout=1800,
            ).returncode
        ok = rc == 0 and (folder / "mesh.blend").exists()
        job.update(state="done" if ok else "error",
                   error=None if ok else f"Blender exited {rc} — see {folder.name}/blender.log")
    except Exception as exc:  # timeout, missing binary
        job.update(state="error", error=str(exc))


class BlenderReq(BaseModel):
    folder: str


@app.post("/api/blender")
def blender(req: BlenderReq):
    folder = _safe_folder(req.folder)
    job = BLENDER_JOBS.get(folder.name)
    if job and job["state"] == "running":
        return job
    BLENDER_JOBS[folder.name] = {"state": "running", "started": time.time(), "error": None}
    threading.Thread(target=_run_blender, args=(folder,), daemon=True).start()
    return BLENDER_JOBS[folder.name]


@app.get("/api/blender/{folder}")
def blender_status(folder: str):
    path = _safe_folder(folder)
    job = BLENDER_JOBS.get(folder)
    if job is None:
        return {"state": "done" if (path / "mesh.blend").exists() else "none", "error": None}
    return job


@app.get("/api/gallery")
def gallery(limit: int = 60):
    items = []
    dirs = sorted((p for p in OUT_ROOT.iterdir() if (p / "splat.ply").exists()),
                  key=lambda p: (p / "splat.ply").stat().st_mtime, reverse=True)
    for p in dirs[:limit]:
        items.append({
            "folder": p.name,
            "preview": (p / "preview.png").exists(),
            "input": (p / "input.png").exists(),
            "mesh": (p / "mesh.blend").exists(),
        })
    return items


def _git_rev() -> str:
    try:
        return subprocess.run(["git", "-C", str(APP_DIR), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        return ""


app.mount("/files", StaticFiles(directory=str(OUT_ROOT)), name="files")
app.mount("/viewer", StaticFiles(directory=str(APP_DIR / "static/viewer")), name="viewer")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
