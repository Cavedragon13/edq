"""Drive Archaeology — web front-end for image_drive.sh (ddrescue-based imaging).

Lists attached block devices (excluding this machine's own system disks),
launches imaging runs, streams their live log to the browser over
Server-Sent Events, and exposes past-run history from log.csv.

Privilege model: this process always runs unprivileged. Imaging runs invoke
`sudo image_drive.sh` under a sudoers rule scoped to that one script path
only (see /etc/sudoers.d/drivearchaeology) — never a broad sudo grant.
"""
import csv
import json
import re
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Dict

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

BASE_DIR = Path("/srv/containers/edq/drive-archaeology")
IMAGES_DIR = BASE_DIR / "images"
LOG_CSV = BASE_DIR / "log.csv"
STATIC_DIR = BASE_DIR / "static"
IMAGE_SCRIPT = BASE_DIR / "scripts" / "image_drive.sh"
WEBUI_LOG_DIR = BASE_DIR / "webui_logs"
WEBUI_LOG_DIR.mkdir(exist_ok=True)
IMAGES_DIR.mkdir(exist_ok=True)

# This machine's own disks — image_drive.sh already refuses these too, but
# the UI should never even offer them as an option.
SYSTEM_DISK_PREFIXES = ("nvme0n1", "nvme1n1")

# ddrescue redraws its progress block with ANSI cursor-up sequences even when
# piped (verified empirically — it doesn't check isatty). Strip those; the
# repeating block itself is harmless and scrolls naturally in a log view.
ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

app = FastAPI(title="Drive Archaeology")

JOBS: Dict[str, dict] = {}
JOBS_LOCK = threading.Lock()


def list_devices():
    try:
        out = subprocess.run(
            ["lsblk", "-J", "-o", "NAME,SIZE,MODEL,SERIAL,TRAN,VENDOR,TYPE,RM"],
            capture_output=True, text=True, check=True, timeout=10,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        raise HTTPException(status_code=500, detail=f"lsblk failed: {e}")

    data = json.loads(out.stdout)
    devices = []
    for entry in data.get("blockdevices", []):
        if entry.get("type") != "disk":
            continue
        name = entry.get("name", "")
        if name.startswith(SYSTEM_DISK_PREFIXES):
            continue
        devices.append({
            "path": f"/dev/{name}",
            "size": entry.get("size"),
            "model": (entry.get("model") or "").strip(),
            "serial": (entry.get("serial") or "").strip(),
            "transport": entry.get("tran"),
            "vendor": (entry.get("vendor") or "").strip(),
            "removable": entry.get("rm"),
        })
    return devices


@app.get("/api/devices")
def api_devices():
    return list_devices()


class StartJobRequest(BaseModel):
    device: str
    label: str


@app.post("/api/jobs")
def api_start_job(req: StartJobRequest):
    label = req.label.strip()
    if not label:
        raise HTTPException(status_code=400, detail="Label is required.")
    if len(label) > 80:
        raise HTTPException(status_code=400, detail="Label too long (max 80 chars).")

    valid_paths = {d["path"] for d in list_devices()}
    if req.device not in valid_paths:
        raise HTTPException(
            status_code=400,
            detail=f"{req.device} is not a currently-attached, eligible device.",
        )

    job_id = uuid.uuid4().hex[:12]
    log_path = WEBUI_LOG_DIR / f"{job_id}.log"

    job = {
        "id": job_id,
        "device": req.device,
        "label": label,
        "status": "running",
        "started_at": time.time(),
        "ended_at": None,
        "returncode": None,
        "lines": [],
        "log_path": str(log_path),
    }
    with JOBS_LOCK:
        JOBS[job_id] = job

    proc = subprocess.Popen(
        ["sudo", str(IMAGE_SCRIPT), "--yes", req.device, label],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    thread = threading.Thread(target=_pump_job_output, args=(job_id, proc, log_path), daemon=True)
    thread.start()

    return {"job_id": job_id}


def _pump_job_output(job_id: str, proc: subprocess.Popen, log_path: Path):
    with open(log_path, "a") as f:
        for raw_line in proc.stdout:
            line = ANSI_RE.sub("", raw_line).rstrip("\n")
            f.write(line + "\n")
            f.flush()
            with JOBS_LOCK:
                JOBS[job_id]["lines"].append(line)
    returncode = proc.wait()
    with JOBS_LOCK:
        job = JOBS[job_id]
        job["status"] = "done" if returncode == 0 else "error"
        job["returncode"] = returncode
        job["ended_at"] = time.time()


@app.get("/api/jobs")
def api_list_jobs():
    with JOBS_LOCK:
        return [
            {k: v for k, v in job.items() if k != "lines"}
            for job in sorted(JOBS.values(), key=lambda j: j["started_at"], reverse=True)
        ]


@app.get("/api/jobs/{job_id}/stream")
def api_stream_job(job_id: str):
    with JOBS_LOCK:
        if job_id not in JOBS:
            raise HTTPException(status_code=404, detail="Unknown job id.")

    def generate():
        idx = 0
        while True:
            with JOBS_LOCK:
                job = JOBS.get(job_id)
                if job is None:
                    yield "event: error\ndata: unknown job\n\n"
                    return
                new_lines = job["lines"][idx:]
                idx += len(new_lines)
                status = job["status"]
            for line in new_lines:
                yield f"data: {json.dumps(line)}\n\n"
            if status != "running":
                yield f"event: done\ndata: {json.dumps(status)}\n\n"
                return
            time.sleep(0.5)

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/api/history")
def api_history():
    if not LOG_CSV.exists():
        return []
    rows = []
    with open(LOG_CSV, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            image_path = row.get("image_path", "")
            run_dir = Path(image_path).parent if image_path else None
            image_exists = bool(image_path and Path(image_path).exists())
            smart_path = run_dir / "smart.txt" if run_dir else None
            smart_exists = bool(smart_path and smart_path.exists())
            row["image_exists"] = image_exists
            row["smart_exists"] = smart_exists
            row["smart_url"] = (
                f"/files/images/{smart_path.relative_to(IMAGES_DIR)}" if smart_exists else None
            )
            row["image_size_bytes"] = Path(image_path).stat().st_size if image_exists else None
            rows.append(row)
    rows.reverse()
    return rows


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


# Read-only access to run artifacts (smart.txt is small/text; image.img files
# are left as server-side paths in the UI rather than browser-download links —
# they can be tens of GB and are meant to stay on this disk).
app.mount("/files/images", StaticFiles(directory=IMAGES_DIR), name="images")
