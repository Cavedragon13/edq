#!/usr/bin/env python3
"""3D Asset Studio — Dragonsuite service (port 8068).

Image -> PBR-textured 3D mesh (GLB) with Pixal3D or TRELLIS.2, run by the local
ComfyUI (:8188) from its official template 3d_pixal3d_trellis2_image_to_model
(built into config/workflows/asset3d_api.json by scripts/asset3d_build_workflow.py).
This server holds no model weights and never touches CUDA itself.

Flow (same shape as TripoSplat Studio):
  1. upload      -> BiRefNet cutout via ComfyUI (skipped if the upload has alpha)
  2. mask edit   -> browser brushes keep/erase on the matte
  3. preview     -> ComfyUI's own ImageCropToMask with the template's settings,
                    i.e. exactly the image the 3D model will be conditioned on
  4. approve     -> full workflow; GLB + PBR maps saved in one readable folder
  5. optional    -> headless Blender import (scripts/glb_to_blender.py)

Outputs: ~/ai_generated/asset3d/<YYYY-MM-DD_HHMMSS>_<name>/
  input.png  mask.png  prepared.png  model.glb  maps/*.png  params.json
  (+ mesh.blend, mesh_front.png, mesh_34.png after the Blender step)
"""
import copy
import datetime
import io
import json
import re
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path

import base64
import numpy as np
import requests
import uvicorn
import websocket
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps
from pydantic import BaseModel, Field

ROOT = Path("/srv/containers/edq")
COMFY = "http://127.0.0.1:8188"
COMFY_WS = "ws://127.0.0.1:8188/ws"
COMFY_OUT = ROOT / "projects/ComfyUI/output"
COMFY_IN = ROOT / "projects/ComfyUI/input"
WORKFLOW = ROOT / "config/workflows/asset3d_api.json"
OUT_ROOT = Path.home() / "ai_generated/asset3d"
HTML = ROOT / "media/asset3d.html"
PORT = 8068
UPLOAD_SUBFOLDER = "asset3d"
MAX_SIDE = 2048            # uploads are downscaled to this; the model sees a 1024 crop anyway

# PreviewImage nodes in the template -> saved map names
MAPS = {"164": "basecolor", "207": "metallic", "208": "roughness",
        "226": "normal", "235": "ambient_occlusion", "262": "uv_atlas"}
# Template seeds are 56/43/42/42; keep their offsets from one user seed.
SEED_OFFSETS = {"3": 14, "12": 1, "18": 0, "23": 0}

OUT_ROOT.mkdir(parents=True, exist_ok=True)
# Sessions live in memory, so uploads left by a previous run are orphans.
shutil.rmtree(COMFY_IN / UPLOAD_SUBFOLDER, ignore_errors=True)
JOB_LOCK = threading.Lock()
SESSIONS: dict[str, dict] = {}
PROGRESS: dict[str, dict] = {}
BLENDER_JOBS: dict[str, dict] = {}
MAX_SESSIONS = 16

app = FastAPI(title="3D Asset Studio")


# ---------------------------------------------------------------- ComfyUI client

class ComfyError(RuntimeError):
    pass


def comfy_up() -> bool:
    try:
        return requests.get(f"{COMFY}/system_stats", timeout=3).ok
    except requests.RequestException:
        return False


def comfy_upload(img: Image.Image, name: str) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    r = requests.post(f"{COMFY}/upload/image",
                      files={"image": (name, buf.getvalue(), "image/png")},
                      data={"subfolder": UPLOAD_SUBFOLDER, "type": "input", "overwrite": "true"},
                      timeout=60)
    r.raise_for_status()
    j = r.json()
    return f"{j['subfolder']}/{j['name']}" if j.get("subfolder") else j["name"]


def comfy_view(item: dict) -> bytes:
    r = requests.get(f"{COMFY}/view", params={
        "filename": item["filename"], "subfolder": item.get("subfolder", ""), "type": item.get("type", "output"),
    }, timeout=120)
    r.raise_for_status()
    return r.content


def comfy_run(prompt: dict, prog: dict | None = None, timeout: int = 1800) -> dict:
    """Queue a prompt, follow it over the websocket, return its history outputs."""
    if not comfy_up():
        raise ComfyError("ComfyUI is not running on :8188 — start it from the dashboard.")
    cid = uuid.uuid4().hex
    ws = websocket.create_connection(f"{COMFY_WS}?clientId={cid}", timeout=30)
    try:
        r = requests.post(f"{COMFY}/prompt", json={"prompt": prompt, "client_id": cid}, timeout=60)
        if not r.ok:
            try:
                detail = r.json()
                errs = detail.get("node_errors") or detail.get("error")
            except ValueError:
                errs = r.text
            raise ComfyError(f"ComfyUI rejected the workflow: {json.dumps(errs)[:600]}")
        pid = r.json()["prompt_id"]
        total = len(prompt)
        done_nodes: set[str] = set()
        deadline = time.time() + timeout
        ws.settimeout(60)
        while time.time() < deadline:
            try:
                msg = ws.recv()
            except websocket.WebSocketTimeoutException:
                continue
            if isinstance(msg, bytes):
                continue  # live preview frames
            m = json.loads(msg)
            data = m.get("data", {})
            if data.get("prompt_id") not in (None, pid):
                continue
            t = m.get("type")
            if t == "executing":
                node = data.get("node")
                if node is None:
                    break
                done_nodes.add(node)
                if prog is not None:
                    cls = prompt.get(node, {}).get("class_type", node)
                    prog.update(node=cls, done=len(done_nodes), total=total, step=0, steps=0)
            elif t == "execution_cached":
                done_nodes.update(data.get("nodes") or [])   # reused from the last run, never "executing"
                if prog is not None:
                    prog.update(done=len(done_nodes), total=total)
            elif t == "progress" and prog is not None:
                prog.update(step=data.get("value", 0), steps=data.get("max", 0))
            elif t == "execution_error":
                raise ComfyError(f"{data.get('node_type')}: {data.get('exception_message', '').strip()[:500]}")
            elif t == "execution_success":
                break
        else:
            raise ComfyError("timed out waiting for ComfyUI")
    finally:
        ws.close()
    hist = requests.get(f"{COMFY}/history/{pid}", timeout=30).json().get(pid, {})
    status = hist.get("status", {})
    if status.get("status_str") == "error":
        raise ComfyError("ComfyUI reported an execution error — see /tmp/comfyui.log")
    return hist.get("outputs", {})


def first_image(outputs: dict, node: str) -> Image.Image:
    items = outputs.get(node, {}).get("images") or []
    if not items:
        raise ComfyError(f"no image from node {node}")
    return Image.open(io.BytesIO(comfy_view(items[0])))


# ---------------------------------------------------------------- helpers

def _png_data_url(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _decode_data_url(data_url: str) -> Image.Image:
    try:
        return Image.open(io.BytesIO(base64.b64decode(data_url.split(",", 1)[1])))
    except Exception as exc:
        raise HTTPException(400, f"bad image data: {exc}")


def _session(sid: str) -> dict:
    s = SESSIONS.get(sid)
    if s is None:
        raise HTTPException(404, "Upload expired — please load the image again.")
    return s


def _drop_session(sid: str):
    s = SESSIONS.pop(sid, None)
    PROGRESS.pop(sid, None)
    if s:
        for key in ("comfy_input", "comfy_mask"):
            if s.get(key):
                (COMFY_IN / s[key]).unlink(missing_ok=True)


def _prune_sessions():
    while len(SESSIONS) > MAX_SESSIONS:
        _drop_session(min(SESSIONS, key=lambda k: SESSIONS[k]["created"]))


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "asset"


def _new_folder(name: str) -> Path:
    base = OUT_ROOT / f"{datetime.datetime.now():%Y-%m-%d_%H%M%S}_{_slug(name)}"
    path, n = base, 2
    while path.exists():
        path = base.with_name(f"{base.name}-{n}")
        n += 1
    path.mkdir(parents=True)
    return path


def _safe_folder(folder: str) -> Path:
    path = (OUT_ROOT / folder).resolve()
    if path.parent != OUT_ROOT.resolve() or not (path / "model.glb").exists():
        raise HTTPException(404, "no such asset folder")
    return path


def _crop_params() -> dict:
    """ImageCropToMask settings straight from the workflow, so preview == model input."""
    wf = json.loads(WORKFLOW.read_text())
    return {k: v for k, v in wf["312"]["inputs"].items() if not isinstance(v, list)}


def _run(label: str, fn):
    with JOB_LOCK:
        try:
            return fn()
        except ComfyError as exc:
            raise HTTPException(502, f"{label}: {exc}")
        except requests.RequestException as exc:
            raise HTTPException(502, f"{label}: ComfyUI unreachable ({exc})")


# ---------------------------------------------------------------- routes

@app.get("/")
def index():
    return FileResponse(HTML)


@app.get("/api/status")
def status():
    return {"comfy": comfy_up()}


@app.post("/api/cutout")
async def cutout(file: UploadFile = File(...)):
    raw = await file.read()
    try:
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGBA")
    except Exception as exc:
        raise HTTPException(400, f"could not read image: {exc}")
    if max(img.size) > MAX_SIDE:
        img.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
    alpha = img.getchannel("A")
    had_alpha = np.asarray(alpha).min() < 255

    sid = uuid.uuid4().hex[:12]
    rgb = img.convert("RGB")
    comfy_input = _run("upload", lambda: comfy_upload(rgb, f"asset3d_{sid}_input.png"))
    if not had_alpha:
        prompt = {
            "1": {"class_type": "LoadImage", "inputs": {"image": comfy_input}},
            "2": {"class_type": "LoadBackgroundRemovalModel", "inputs": {"bg_removal_name": "birefnet.safetensors"}},
            "3": {"class_type": "RemoveBackground", "inputs": {"bg_removal_model": ["2", 0], "image": ["1", 0]}},
            "4": {"class_type": "MaskToImage", "inputs": {"mask": ["3", 0]}},
            "5": {"class_type": "PreviewImage", "inputs": {"images": ["4", 0]}},
        }
        alpha = _run("background removal", lambda: first_image(comfy_run(prompt), "5")).convert("L")
        if alpha.size != img.size:
            alpha = alpha.resize(img.size, Image.BILINEAR)

    SESSIONS[sid] = {"created": time.time(), "name": Path(file.filename or "asset").stem,
                     "input": img, "rgb": rgb, "comfy_input": comfy_input}
    _prune_sessions()
    return {"id": sid, "name": SESSIONS[sid]["name"], "width": img.width, "height": img.height,
            "had_alpha": bool(had_alpha), "image": _png_data_url(rgb), "mask": _png_data_url(alpha)}


class PrepareReq(BaseModel):
    id: str
    mask: str   # PNG data URL, white = keep


@app.post("/api/prepare")
def prepare(req: PrepareReq):
    s = _session(req.id)
    mask = _decode_data_url(req.mask).convert("L")
    if mask.size != s["rgb"].size:
        mask = mask.resize(s["rgb"].size, Image.BILINEAR)
    if np.asarray(mask).max() == 0:
        raise HTTPException(400, "The mask is empty — paint back the subject first.")
    comfy_mask = _run("upload", lambda: comfy_upload(mask.convert("RGB"), f"asset3d_{req.id}_mask.png"))
    prompt = {
        "1": {"class_type": "LoadImage", "inputs": {"image": s["comfy_input"]}},
        "2": {"class_type": "LoadImageMask", "inputs": {"image": comfy_mask, "channel": "red"}},
        "3": {"class_type": "ImageCropToMask", "inputs": {"images": ["1", 0], "masks": ["2", 0], **_crop_params()}},
        "4": {"class_type": "PreviewImage", "inputs": {"images": ["3", 0]}},
    }
    prepared = _run("preview", lambda: first_image(comfy_run(prompt), "4")).convert("RGB")
    s.update(mask=mask, comfy_mask=comfy_mask, prepared=prepared)
    return {"prepared": _png_data_url(prepared)}


class GenerateReq(BaseModel):
    id: str
    name: str = ""
    model: str = Field("pixal3d", pattern="^(pixal3d|trellis2)$")
    seed: int = Field(42, ge=0, le=2**31)
    resolution: int = Field(1536, ge=1024, le=2048, multiple_of=128)
    texture: int = Field(4096, ge=1024, le=8192)
    faces: int = Field(700000, ge=10000, le=5000000)


@app.post("/api/generate")
def generate(req: GenerateReq):
    s = _session(req.id)
    if "prepared" not in s:
        raise HTTPException(400, "Preview the model input first, then approve.")
    prog = PROGRESS[req.id] = {"stage": "queued", "node": "", "done": 0, "total": 0, "step": 0, "steps": 0,
                               "started": time.time()}

    wf = json.loads(WORKFLOW.read_text())
    p = copy.deepcopy(wf)
    p["122"]["inputs"]["image"] = s["comfy_input"]
    p["900"]["inputs"]["image"] = s["comfy_mask"]
    p["248"]["inputs"]["switch"] = False                      # use the studio mask
    p["316"]["inputs"]["value"] = req.model == "trellis2"     # template: true = TRELLIS.2
    for nid, off in SEED_OFFSETS.items():
        p[nid]["inputs"]["seed"] = req.seed + off
    p["94"]["inputs"]["target_resolution"] = req.resolution
    p["288"]["inputs"]["value"] = req.texture
    p["186"]["inputs"]["target_face_count"] = req.faces
    run_tag = uuid.uuid4().hex[:8]
    p["322"]["inputs"]["filename_prefix"] = f"asset3d/{run_tag}/model"

    def job():
        prog["stage"] = "running"
        t0 = time.time()
        outputs = comfy_run(p, prog)
        return outputs, time.time() - t0

    outputs, secs = _run("generation", job)
    prog["stage"] = "saving"

    glbs = outputs.get("322", {}).get("3d") or []
    if not glbs:
        raise HTTPException(502, "ComfyUI finished but produced no GLB")
    name = req.name.strip() or s["name"]
    folder = _new_folder(name)
    (folder / "model.glb").write_bytes(comfy_view(glbs[0]))
    s["input"].save(folder / "input.png")
    s["mask"].save(folder / "mask.png")
    s["prepared"].save(folder / "prepared.png")
    (folder / "maps").mkdir()
    for nid, label in MAPS.items():
        items = outputs.get(nid, {}).get("images") or []
        if items:
            (folder / "maps" / f"{label}.png").write_bytes(comfy_view(items[0]))
    # one copy only: drop ComfyUI's duplicate of the GLB
    shutil.rmtree(COMFY_OUT / "asset3d" / run_tag, ignore_errors=True)

    params = req.model_dump(exclude={"id"}) | {
        "name": name,
        "model_label": "Pixal3D" if req.model == "pixal3d" else "TRELLIS.2",
        "seconds": round(secs, 1),
        "created": datetime.datetime.now().isoformat(timespec="seconds"),
        "workflow": "ComfyUI template 3d_pixal3d_trellis2_image_to_model (int8)",
        "glb_bytes": (folder / "model.glb").stat().st_size,
    }
    (folder / "params.json").write_text(json.dumps(params, indent=2))
    (OUT_ROOT / "latest.json").write_text(json.dumps({"folder": folder.name, **params}, indent=2))
    prog["stage"] = "done"
    return {"folder": folder.name, "seconds": params["seconds"], "glb_mb": round(params["glb_bytes"] / 1e6, 1)}


@app.get("/api/progress/{sid}")
def progress(sid: str):
    p = PROGRESS.get(sid)
    if not p:
        return {"stage": "idle"}
    return p | {"elapsed": round(time.time() - p["started"])}


def _blender_bin() -> str:
    exe = shutil.which("blender") or "/snap/bin/blender"
    if not Path(exe).exists():
        raise HTTPException(500, "Blender not found (expected on PATH or /snap/bin/blender)")
    return exe


def _run_blender(folder: Path):
    job = BLENDER_JOBS[folder.name]
    try:
        with open(folder / "blender.log", "w") as fh:
            rc = subprocess.run(
                [_blender_bin(), "-b", "--python", str(ROOT / "scripts/glb_to_blender.py"), "--", str(folder)],
                stdout=fh, stderr=subprocess.STDOUT, timeout=1800,
            ).returncode
        ok = rc == 0 and (folder / "mesh.blend").exists()
        job.update(state="done" if ok else "error",
                   error=None if ok else f"Blender exited {rc} — see {folder.name}/blender.log")
    except Exception as exc:
        job.update(state="error", error=str(exc))


class BlenderReq(BaseModel):
    folder: str


@app.post("/api/blender")
def blender(req: BlenderReq):
    folder = _safe_folder(req.folder)
    job = BLENDER_JOBS.get(folder.name)
    if job and job["state"] == "running":
        return job
    BLENDER_JOBS[folder.name] = {"state": "running", "error": None}
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
    dirs = sorted((p for p in OUT_ROOT.iterdir() if (p / "model.glb").exists()),
                  key=lambda p: (p / "model.glb").stat().st_mtime, reverse=True)
    items = []
    for p in dirs[:limit]:
        try:
            params = json.loads((p / "params.json").read_text())
        except Exception:
            params = {}
        items.append({"folder": p.name, "model": params.get("model_label", ""),
                      "mesh": (p / "mesh.blend").exists(), "maps": sorted(x.stem for x in (p / "maps").glob("*.png"))})
    return items


app.mount("/files", StaticFiles(directory=str(OUT_ROOT)), name="files")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
