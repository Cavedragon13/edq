#!/usr/bin/env python3
"""
Dragonsuite v2 - Project Dashboard Backend
FastAPI server for managing and monitoring AI projects
"""

import json
import socket
import subprocess
import os
import signal
from pathlib import Path
from typing import Optional
from datetime import datetime
import io

from fastapi import FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
import uvicorn
import psutil

# Optional QR code support
try:
    import qrcode
    from PIL import Image
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False

app = FastAPI(title="Dragonsuite v2", description="AI Project Dashboard")

# Paths
BASE_DIR = Path("/srv/containers/edq")
CONFIG_PATH = BASE_DIR / "config" / "dragonsuite.json"
MEDIA_DIR = BASE_DIR / "media"
PROJECTS_DIR = BASE_DIR / "projects"


def get_local_ip() -> str:
    """Auto-detect the local IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.1)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def load_config() -> dict:
    """Load configuration from JSON file."""
    if not CONFIG_PATH.exists():
        return {"services": [], "categories": {}}

    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def check_port(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a port is open (service running)."""
    if port is None or port == 0:
        return False

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def get_git_info(project_path: str) -> Optional[dict]:
    """Get git revision info for a project."""
    path = Path(project_path)
    if not path.exists():
        return None

    git_dir = path / ".git"
    if not git_dir.exists():
        return None

    try:
        # Get short commit hash
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            return None

        commit_hash = result.stdout.strip()

        # Get branch name
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=5
        )
        branch = result.stdout.strip() if result.returncode == 0 else "unknown"

        # Get last commit date
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cr"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=5
        )
        last_commit = result.stdout.strip() if result.returncode == 0 else "unknown"

        return {
            "hash": commit_hash,
            "branch": branch,
            "last_commit": last_commit
        }
    except Exception as e:
        return {"error": str(e)}


# API Endpoints

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    """Serve the dashboard HTML."""
    html_path = MEDIA_DIR / "dragonsuite.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Dashboard HTML not found")
    return FileResponse(html_path)


@app.get("/api/config")
async def get_config():
    """Get full configuration."""
    config = load_config()
    config["local_ip"] = get_local_ip()
    return config


@app.get("/api/status")
async def get_all_status():
    """Check status of all services."""
    config = load_config()
    local_ip = get_local_ip()

    gpu_procs = get_vram_per_process()

    statuses = []
    for service in config.get("services", []):
        port = service.get("port")
        always_on = service.get("always_on", False)
        is_running = True if always_on else (check_port(port) if port else False)

        # Live VRAM: match GPU processes to this service via project_path
        live_vram_gb = None
        project_path = service.get("project_path", "")
        if is_running and project_path and gpu_procs:
            matched_mb = sum(
                p["vram_mb"] for p in gpu_procs
                if project_path in p["cmdline"]
            )
            if matched_mb:
                live_vram_gb = round(matched_mb / 1024, 1)

        # Build URL — use explicit url field if set (for external-host services)
        url = service.get("url") or None
        if not url and port:
            url = f"http://{local_ip}:{port}"
            if service.get("path"):
                url += service["path"]

        statuses.append({
            "id": service.get("id"),
            "name": service.get("name"),
            "running": is_running,
            "always_on": always_on,
            "port": port,
            "url": url,
            "category": service.get("category"),
            "description": service.get("description"),
            "launch_command": service.get("launch_command"),
            "project_path": service.get("project_path"),
            "icon": service.get("icon"),
            "thumbnail": service.get("thumbnail"),
            "github_url": service.get("github_url"),
            "pages_url": service.get("pages_url"),
            "features": service.get("features", []),
            "vram_gb": service.get("vram_gb"),
            "live_vram_gb": live_vram_gb,
            "output_dir": service.get("output_dir"),
        })

    return {
        "local_ip": local_ip,
        "services": statuses
    }


@app.get("/api/qrcode/{service_id}")
async def get_qrcode(service_id: str):
    """Generate QR code for a service URL."""
    if not HAS_QRCODE:
        raise HTTPException(status_code=501, detail="QR code support not installed. Install with: pip install qrcode[pil]")

    config = load_config()
    local_ip = get_local_ip()

    # Find service
    service = None
    for s in config.get("services", []):
        if s.get("id") == service_id:
            service = s
            break

    if not service:
        raise HTTPException(status_code=404, detail=f"Service '{service_id}' not found")

    port = service.get("port")

    # Build URL — use explicit url field if set (for external-host services)
    url = service.get("url") or None
    if not url:
        if not port:
            raise HTTPException(status_code=400, detail="Service has no port configured")
        url = f"http://{local_ip}:{port}"
        if service.get("path"):
            url += service["path"]

    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # Convert to bytes
    img_buffer = io.BytesIO()
    img.save(img_buffer, format="PNG")
    img_buffer.seek(0)

    return Response(content=img_buffer.getvalue(), media_type="image/png")


@app.get("/api/git/{service_id}")
async def get_git_revision(service_id: str):
    """Get git revision info for a service's project."""
    config = load_config()

    # Find service
    service = None
    for s in config.get("services", []):
        if s.get("id") == service_id:
            service = s
            break

    if not service:
        raise HTTPException(status_code=404, detail=f"Service '{service_id}' not found")

    project_path = service.get("project_path")
    if not project_path:
        return {"git": None, "message": "No project path configured"}

    git_info = get_git_info(project_path)
    if git_info is None:
        return {"git": None, "message": "Not a git repository"}

    return {"git": git_info}


@app.get("/api/llm-models")
async def get_llm_models():
    """Query installed models from Ollama and LM Studio (if running)."""
    import urllib.request, json as _json

    result = {}

    # Ollama — GET /api/tags
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2) as r:
            data = _json.loads(r.read())
        result["ollama"] = [
            {
                "name": m["name"],
                "size_gb": round(m.get("size", 0) / 1e9, 1),
            }
            for m in data.get("models", [])
        ]
    except Exception:
        result["ollama"] = None  # not running or unreachable

    # LM Studio — OpenAI-compatible GET /v1/models
    try:
        with urllib.request.urlopen("http://127.0.0.1:1234/v1/models", timeout=2) as r:
            data = _json.loads(r.read())
        result["lmstudio"] = [m["id"] for m in data.get("data", [])]
    except Exception:
        result["lmstudio"] = None

    return result


@app.get("/api/gpu-stats")
async def get_gpu_stats():
    """Get GPU VRAM, utilization, and temperature stats using nvidia-smi."""
    try:
        cmd = [
            "nvidia-smi",
            "--query-gpu=memory.used,memory.total,utilization.gpu,temperature.gpu",
            "--format=csv,noheader,nounits"
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode != 0:
            return {"error": "nvidia-smi failed"}

        output = result.stdout.strip()
        parts = [x.strip() for x in output.split(',')]

        if len(parts) != 4:
            return {"error": "Unexpected nvidia-smi output"}

        vram_used_mb = int(parts[0])
        vram_total_mb = int(parts[1])
        gpu_util = int(parts[2])
        gpu_temp = int(parts[3])

        vram_percent = (vram_used_mb / vram_total_mb * 100) if vram_total_mb > 0 else 0

        return {
            "vram_used_mb": vram_used_mb,
            "vram_total_mb": vram_total_mb,
            "vram_percent": vram_percent,
            "gpu_utilization": gpu_util,
            "gpu_temp": gpu_temp
        }

    except subprocess.TimeoutExpired:
        return {"error": "nvidia-smi timeout"}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/system-stats")
async def get_system_stats():
    """Get CPU, RAM, and disk usage stats."""
    try:
        cpu_percent = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory()

        # Check both root and project SSD
        root_disk = psutil.disk_usage('/')
        disks = {
            "root": {
                "used_gb": round(root_disk.used / (1024**3), 1),
                "total_gb": round(root_disk.total / (1024**3), 1),
                "percent": round(root_disk.percent, 1),
                "mount": "/"
            }
        }

        # Project SSD (separate mount)
        try:
            proj_disk = psutil.disk_usage('/srv/containers')
            # Only add if it's a different filesystem
            if proj_disk.total != root_disk.total:
                disks["projects"] = {
                    "used_gb": round(proj_disk.used / (1024**3), 1),
                    "total_gb": round(proj_disk.total / (1024**3), 1),
                    "percent": round(proj_disk.percent, 1),
                    "mount": "/srv/containers"
                }
        except Exception:
            pass

        # Primary disk stats (project SSD if available, else root)
        primary = disks.get("projects", disks["root"])

        return {
            "cpu_percent": cpu_percent,
            "ram_used_gb": round(ram.used / (1024**3), 1),
            "ram_total_gb": round(ram.total / (1024**3), 1),
            "ram_percent": ram.percent,
            "disk_used_gb": primary["used_gb"],
            "disk_total_gb": primary["total_gb"],
            "disk_percent": primary["percent"],
            "disks": disks
        }
    except Exception as e:
        return {"error": str(e)}


def find_process_by_port(port: int) -> Optional[int]:
    """Find process ID using a specific port."""
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            # Could be multiple PIDs, get the first one
            pids = result.stdout.strip().split('\n')
            return int(pids[0])
    except Exception:
        pass
    return None


def kill_all_on_port(port: int) -> list[int]:
    """Kill all processes (and their process groups) holding a port. Returns killed PIDs."""
    killed = []
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0 or not result.stdout.strip():
            return killed
        pids = [int(p) for p in result.stdout.strip().split('\n') if p.strip()]
        # SIGTERM first for graceful shutdown
        for pid in pids:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        import time
        time.sleep(2)
        # SIGKILL any survivors + their process groups
        for pid in pids:
            try:
                os.kill(pid, 0)  # check if still alive
                try:
                    pgid = os.getpgid(pid)
                    os.killpg(pgid, signal.SIGKILL)
                except Exception:
                    os.kill(pid, signal.SIGKILL)
                killed.append(pid)
            except ProcessLookupError:
                killed.append(pid)  # already gone, counts as killed
    except Exception:
        pass
    return killed


def get_vram_free_gb() -> float:
    """Return free VRAM in GB, or -1 if nvidia-smi unavailable."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return int(result.stdout.strip()) / 1024
    except Exception:
        pass
    return -1


def get_vram_per_process() -> list:
    """Return [{pid, vram_mb, cmdline}] for all GPU-using processes via nvidia-smi."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid,used_memory",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return []
        entries = []
        for line in result.stdout.strip().splitlines():
            parts = [x.strip() for x in line.split(',')]
            if len(parts) != 2:
                continue
            try:
                pid = int(parts[0])
                vram_mb = int(parts[1])
            except ValueError:
                continue
            # Get full cmdline for project_path matching
            try:
                cmdline = open(f"/proc/{pid}/cmdline").read().replace("\x00", " ").strip()
            except Exception:
                cmdline = ""
            entries.append({"pid": pid, "vram_mb": vram_mb, "cmdline": cmdline})
        return entries
    except Exception:
        return []


def get_competing_gpu_services(config: dict, needed_gb: float) -> list[dict]:
    """Return running GPU services that are eating into needed VRAM headroom."""
    competing = []
    free_gb = get_vram_free_gb()
    if free_gb < 0 or free_gb >= needed_gb + 1:  # +1GB buffer
        return competing
    for s in config.get("services", []):
        if not s.get("vram_gb") or not s.get("port"):
            continue
        if check_port(s["port"]):
            competing.append({"name": s["name"], "port": s["port"], "vram_gb": s["vram_gb"]})
    return competing


@app.post("/api/start/{service_id}")
async def start_service(service_id: str, force: bool = False):
    """Start a service by running its launch command."""
    config = load_config()

    # Find service
    service = None
    for s in config.get("services", []):
        if s.get("id") == service_id:
            service = s
            break

    if not service:
        raise HTTPException(status_code=404, detail=f"Service '{service_id}' not found")

    launch_command = service.get("launch_command")
    if not launch_command:
        raise HTTPException(status_code=400, detail="Service has no launch command configured")

    port = service.get("port")
    if port and check_port(port):
        return {"status": "already_running", "message": f"{service['name']} is already running on port {port}"}

    # VRAM pre-check for GPU services
    vram_needed = service.get("vram_gb", 0)
    if vram_needed and not force:
        competing = get_competing_gpu_services(config, vram_needed)
        if competing:
            free_gb = get_vram_free_gb()
            names = ", ".join(f"{s['name']} ({s['vram_gb']}GB)" for s in competing)
            return {
                "status": "vram_warning",
                "message": f"Only {free_gb:.1f}GB VRAM free, {vram_needed}GB needed. Running GPU services: {names}. Stop them first or use force=true to start anyway.",
                "competing": competing,
                "vram_free_gb": free_gb,
                "vram_needed_gb": vram_needed,
            }

    try:
        # Run in background with nohup
        subprocess.Popen(
            f"nohup bash -c '{launch_command}' > /tmp/dragonsuite_{service_id}.log 2>&1 &",
            shell=True,
            cwd="/srv/containers/edq",
            start_new_session=True
        )
        return {"status": "started", "message": f"Starting {service['name']}..."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start service: {str(e)}")


@app.post("/api/stop/{service_id}")
async def stop_service(service_id: str):
    """Stop a service by killing its process."""
    config = load_config()

    # Find service
    service = None
    for s in config.get("services", []):
        if s.get("id") == service_id:
            service = s
            break

    if not service:
        raise HTTPException(status_code=404, detail=f"Service '{service_id}' not found")

    port = service.get("port")
    stop_command = service.get("stop_command")
    if not port and not stop_command:
        raise HTTPException(status_code=400, detail="Service has no port or stop command configured - cannot stop")

    if port and not check_port(port) and not stop_command:
        return {"status": "not_running", "message": f"{service['name']} is not running"}

    try:
        if stop_command:
            subprocess.run(stop_command, shell=True, cwd="/srv/containers/edq", timeout=15)
            if port:
                kill_all_on_port(port)  # clean up anything still on the primary port
            return {"status": "stopped", "message": f"Stopped {service['name']}"}
        killed = kill_all_on_port(port)
        if not killed:
            raise HTTPException(status_code=500, detail="Could not find process to stop")
        return {"status": "stopped", "message": f"Stopped {service['name']} (PIDs: {killed})"}
    except HTTPException:
        raise
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied to stop process")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop service: {str(e)}")


@app.get("/api/pollen")
async def get_pollen():
    """Proxy Google Pollen API — keeps API key server-side. KPSM coords (Portsmouth NH)."""
    import urllib.request as _ur
    from dotenv import load_dotenv as _lde
    _lde(BASE_DIR / ".env")
    key = os.getenv("STREET_VIEW_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
    if not key:
        raise HTTPException(status_code=503, detail="STREET_VIEW_API_KEY not configured in .env")
    lat, lng = 43.0789, -70.8203  # KPSM · Portsmouth NH
    url = (
        f"https://pollen.googleapis.com/v1/forecast:lookup"
        f"?location.latitude={lat}&location.longitude={lng}&days=5&key={key}"
    )
    try:
        with _ur.urlopen(url, timeout=8) as r:
            return json.loads(r.read())
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


CRON_JOBS = [
    ("commit",  "nightly commit",  "logs/nightly_commit_cron.log"),
    ("backup",  "backup",          "logs/nightly_backup_cron.log"),
    ("publish", "publish queue",   "logs/publish_queue_cron.log"),
    ("skills",  "sync skills",     "logs/sync_skills_cron.log"),
    ("lint",    "kb lint",         "logs/lint_kb_cron.log"),
    ("weekly",  "weekly update",   "logs/weekly_update.log"),
]


@app.get("/api/cron-logs")
async def get_cron_logs():
    """Return last-run status and tail for each nightly cron job."""
    result = []
    for key, name, rel_path in CRON_JOBS:
        p = BASE_DIR / rel_path
        entry: dict = {"key": key, "name": name, "exists": p.exists()}
        if p.exists():
            mtime = p.stat().st_mtime
            entry["last_run_ts"] = mtime
            entry["last_run"] = datetime.fromtimestamp(mtime).strftime("%m/%d %H:%M")
            lines = [l for l in p.read_text(errors="replace").splitlines() if l.strip()]
            tail = lines[-30:]
            entry["tail"] = "\n".join(tail)
            bad = any(w in "\n".join(lines[-5:]).lower() for w in ("error", "traceback", "exception", "failed", "fail:"))
            entry["status"] = "error" if bad else "ok"
        result.append(entry)
    return result


# Mount media directory for static files (favicon, etc.)
app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")


def main():
    """Run the server."""
    local_ip = get_local_ip()
    port = 8100

    print(f"\n{'='*50}")
    print(f"  Dragonsuite v2 - Project Dashboard")
    print(f"{'='*50}")
    print(f"\n  Local:   http://localhost:{port}")
    print(f"  Network: http://{local_ip}:{port}")
    print(f"\n{'='*50}\n")

    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
