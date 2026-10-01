#!/usr/bin/env python3
"""Dashboard service for the full upstream Mira-Scene pipeline (port 8071).

One image in -> segmentation (SAM3 + Gemini scene graph) -> depth -> CCM -> object meshes
(SAM-3D) -> floor -> gravity-aware scene assembly -> environment panorama.  The server itself
holds no GPU memory: each job runs ``scripts/run_mira_pipeline.sh`` as a detached process whose
stages load and release the GPU one at a time.  Jobs are serialized.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import time
from datetime import datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

ROOT = Path("/srv/containers/edq")
OUTPUT_DIR = Path("/home/edq/ai_generated/mira-scene")
RUNNER = ROOT / "scripts/run_mira_pipeline.sh"
PORT = 8071
MIN_FREE_VRAM_MIB = 13000
# Stage -> output file (relative to the case dir) whose existence marks it complete.
STAGES = [
    ("segmentation", "scene_graph.json"),
    ("depth", "depth/ppd/depth.npy"),
    ("ccm", "CCM/masks.npy"),
    ("mesh", "mesh/sam3d/000.glb"),
    ("floor", "floor/floor_plane.glb"),
    ("scene", "scene/sam3d/ppd_depth/scene.glb"),
    ("environment", "environment/environment_equirect.png"),
]
DELIVERABLES = [
    ("scene_with_floor", "Scene + floor (GLB)", "scene/sam3d/ppd_depth/scene_with_floor.glb"),
    ("scene", "Scene (GLB)", "scene/sam3d/ppd_depth/scene.glb"),
    ("environment", "Environment panorama", "environment/environment_equirect.png"),
    ("floor", "Floor plane (GLB)", "floor/floor_plane.glb"),
    ("scene_graph", "Scene graph (JSON)", "scene_graph.json"),
    ("source", "Input", "input/scene.png"),
]

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
app = FastAPI(title="Mira Scene")


def _job_dir(job_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", job_id):
        raise HTTPException(404, "job not found")
    path = (OUTPUT_DIR / job_id).resolve()
    if path.parent != OUTPUT_DIR.resolve() or not (path / "job.json").is_file():
        raise HTTPException(404, "job not found")
    return path


def _read(path: Path) -> dict:
    return json.loads((path / "job.json").read_text())


def _write(path: Path, data: dict) -> None:
    tmp = path / ".job.json.tmp"
    tmp.write_text(json.dumps(data, indent=2))
    os.replace(tmp, path / "job.json")


def _alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:
        # A zombie is finished for our purposes.
        return Path(f"/proc/{pid}/stat").read_text().split(")")[-1].split()[0] != "Z"
    except OSError:
        return False


def _case_dir(job: Path, meta: dict) -> Path:
    return job / "out" / meta["case"]


def _state(job: Path) -> dict:
    meta = _read(job)
    case = _case_dir(job, meta)
    done = [name for name, rel in STAGES if (case / rel).exists()]
    running = _alive(meta.get("pid"))
    if meta["status"] == "running" and not running:
        # Process ended: success if the last stage produced its output, otherwise failure.
        meta["status"] = "done" if len(done) == len(STAGES) else "failed"
        meta["finished_at"] = datetime.now().isoformat(timespec="seconds")
        _write(job, meta)
    current = next((name for name, _ in STAGES if name not in done), None)
    meta["stages"] = [
        {"name": name, "state": "done" if name in done else
         ("running" if meta["status"] == "running" and name == current else "pending")}
        for name, _ in STAGES
    ]
    meta["files"] = [
        {"key": key, "label": label, "url": f"/files/{job.name}/out/{meta['case']}/{rel}"}
        for key, label, rel in DELIVERABLES if (case / rel).exists()
    ]
    mesh_dir = case / "mesh/sam3d"
    meta["objects"] = []
    if mesh_dir.is_dir():
        names = {}
        graph = case / "scene_graph.json"
        if graph.is_file():
            try:
                for node in json.loads(graph.read_text()).get("nodes", []):
                    match = re.fullmatch(r"object_(\d+)", str(node.get("id", "")))
                    if match and node.get("name"):
                        names[int(match.group(1))] = str(node["name"])
            except (ValueError, OSError, AttributeError):
                pass
        for glb in sorted(mesh_dir.glob("[0-9][0-9][0-9].glb")):
            meta["objects"].append({"name": names.get(int(glb.stem), glb.stem),
                                    "url": f"/files/{job.name}/out/{meta['case']}/mesh/sam3d/{glb.name}"})
    log = job / "run.log"
    meta["log_tail"] = log.read_text(errors="replace")[-1500:] if log.is_file() else ""
    return meta


def _free_vram_mib() -> int | None:
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10).stdout.strip().splitlines()
        return int(out[0])
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return None


def _running_job() -> str | None:
    for path in OUTPUT_DIR.glob("*/job.json"):
        try:
            meta = json.loads(path.read_text())
        except ValueError:
            continue
        if meta.get("status") == "running" and _alive(meta.get("pid")):
            return path.parent.name
    return None


@app.get("/health")
def health():
    return {"ok": RUNNER.is_file(), "service": "mira-scene", "running_job": _running_job()}


@app.post("/api/jobs")
async def create_job(image: UploadFile = File(...)):
    active = _running_job()
    if active:
        raise HTTPException(409, f"Job {active} is still running; Mira processes one scene at a time.")
    free = _free_vram_mib()
    if free is not None and free < MIN_FREE_VRAM_MIB:
        raise HTTPException(507, f"Only {free} MiB VRAM free; Mira needs ~{MIN_FREE_VRAM_MIB}. "
                                 "Stop other GPU services first.")
    data = await image.read()
    suffix = Path(image.filename or "scene.png").suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(400, "Upload a PNG, JPG or WebP image.")
    slug = re.sub(r"[^A-Za-z0-9]+", "-", Path(image.filename or "scene").stem).strip("-").lower()[:40] or "scene"
    job_id = f"mira_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{slug}"
    job = OUTPUT_DIR / job_id
    (job / "in").mkdir(parents=True)
    (job / "in" / f"{slug}{suffix}").write_bytes(data)
    log = open(job / "run.log", "wb")
    process = subprocess.Popen(
        ["bash", str(RUNNER), str(job / "in"), str(job / "out")],
        cwd=str(ROOT), stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    _write(job, {"id": job_id, "case": slug, "status": "running", "pid": process.pid,
                 "started_at": datetime.now().isoformat(timespec="seconds"), "input": image.filename})
    (OUTPUT_DIR / "latest.json").write_text(json.dumps({"job": job_id}))
    return {"ok": True, "job": job_id, "url": f"/api/jobs/{job_id}"}


@app.get("/api/jobs")
def list_jobs():
    jobs = []
    for path in sorted(OUTPUT_DIR.glob("*/job.json"), reverse=True)[:30]:
        try:
            state = _state(path.parent)
        except (ValueError, KeyError, OSError):
            continue
        jobs.append({k: state[k] for k in ("id", "status", "started_at", "input")}
                    | {"stages_done": sum(s["state"] == "done" for s in state["stages"]),
                       "stages_total": len(STAGES)})
    return {"jobs": jobs}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    return _state(_job_dir(job_id))


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    job = _job_dir(job_id)
    meta = _read(job)
    pid = meta.get("pid")
    if meta["status"] == "running" and _alive(pid):
        os.killpg(os.getpgid(pid), signal.SIGTERM)
        time.sleep(2)
        if _alive(pid):
            os.killpg(os.getpgid(pid), signal.SIGKILL)
    meta["status"] = "cancelled"
    meta["finished_at"] = datetime.now().isoformat(timespec="seconds")
    _write(job, meta)
    return {"ok": True}


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str):
    job = _job_dir(job_id)
    if _read(job)["status"] == "running":
        raise HTTPException(409, "Cancel the job before deleting it.")
    shutil.rmtree(job)
    return {"ok": True}


@app.get("/files/{job_id}/{rest:path}")
def files(job_id: str, rest: str):
    job = _job_dir(job_id)
    path = (job / rest).resolve()
    if job.resolve() not in path.parents or not path.is_file():
        raise HTTPException(404, "file not found")
    return FileResponse(path)


@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse((ROOT / "media/mira_scene.html").read_text())


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
