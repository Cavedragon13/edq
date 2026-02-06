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
import io

from fastapi import FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
import uvicorn

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

    statuses = []
    for service in config.get("services", []):
        port = service.get("port")
        is_running = check_port(port) if port else False

        # Build URL
        url = None
        if port:
            url = f"http://{local_ip}:{port}"
            if service.get("path"):
                url += service["path"]

        statuses.append({
            "id": service.get("id"),
            "name": service.get("name"),
            "running": is_running,
            "port": port,
            "url": url,
            "category": service.get("category"),
            "description": service.get("description"),
            "launch_command": service.get("launch_command"),
            "project_path": service.get("project_path"),
            "icon": service.get("icon")
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
    if not port:
        raise HTTPException(status_code=400, detail="Service has no port configured")

    # Build URL
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


@app.post("/api/start/{service_id}")
async def start_service(service_id: str):
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
    if not port:
        raise HTTPException(status_code=400, detail="Service has no port configured - cannot stop")

    if not check_port(port):
        return {"status": "not_running", "message": f"{service['name']} is not running"}

    pid = find_process_by_port(port)
    if not pid:
        raise HTTPException(status_code=500, detail="Could not find process to stop")

    try:
        os.kill(pid, signal.SIGTERM)
        return {"status": "stopped", "message": f"Stopped {service['name']} (PID {pid})"}
    except ProcessLookupError:
        return {"status": "not_running", "message": "Process already stopped"}
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied to stop process")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop service: {str(e)}")


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
