#!/usr/bin/env python3
"""
Dragonsuite MCP Server

Tools for managing Dragonsuite services. All service definitions
are read live from config/dragonsuite.json — no hardcoded lists.

Tools:
  dragonsuite_status     - All services + live port check + VRAM
  dragonsuite_vram       - GPU VRAM details
  dragonsuite_start      - Start a service (logs to /tmp/dragonsuite_logs/<id>.log)
  dragonsuite_stop       - Stop a service using its stop_command
  dragonsuite_logs       - Tail a service log (only if started via this server)
  dragonsuite_check_port - Check what process (if any) is on an arbitrary port
  dragonsuite_kill_port  - Kill whatever is on a port (for orphaned processes)
  dragonsuite_processes  - Show all GPU/Python processes and their ports
"""

import asyncio
import json
import subprocess
import re
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

BASE_DIR = Path("/srv/containers/edq")
CONFIG_FILE = BASE_DIR / "config" / "dragonsuite.json"
LOG_DIR = Path("/tmp/dragonsuite_logs")

server = Server("dragonsuite")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_services() -> list[dict]:
    """Load service list from dragonsuite.json."""
    try:
        data = json.loads(CONFIG_FILE.read_text())
        return data.get("services", [])
    except Exception as e:
        return []


def service_ids() -> list[str]:
    return [s["id"] for s in load_services()]


def find_service(service_id: str) -> dict | None:
    for svc in load_services():
        if svc["id"] == service_id:
            return svc
    return None


def check_port(port: int) -> bool:
    """Return True if something is listening on the port."""
    if not port:
        return False
    try:
        result = subprocess.run(
            ["ss", "-tlnp", f"sport = :{port}"],
            capture_output=True, text=True, timeout=5,
        )
        lines = result.stdout.strip().split("\n")
        return len(lines) > 1  # header + at least one data line
    except Exception:
        return False


def process_on_port(port: int) -> str | None:
    """Return process name listening on port, or None."""
    try:
        result = subprocess.run(
            ["ss", "-tlnp", f"sport = :{port}"],
            capture_output=True, text=True, timeout=5,
        )
        match = re.search(r'users:\(\("([^"]+)"', result.stdout)
        return match.group(1) if match else None
    except Exception:
        return None


def get_vram() -> dict:
    try:
        result = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=memory.used,memory.total,memory.free,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(",")
            used, total, free, util = [int(p.strip()) for p in parts]
            return {
                "used_mb": used, "total_mb": total, "free_mb": free,
                "gpu_util_percent": util,
                "used_percent": round(used / total * 100, 1),
            }
    except Exception as e:
        return {"error": str(e)}
    return {"error": "nvidia-smi failed"}


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

@server.list_tools()
async def list_tools() -> list[Tool]:
    ids = service_ids()
    ids_with_launch = [s["id"] for s in load_services() if s.get("launch_command")]
    ids_with_stop = [s["id"] for s in load_services() if s.get("stop_command")]

    return [
        Tool(
            name="dragonsuite_status",
            description=(
                "List all Dragonsuite services with live port status and current GPU VRAM. "
                "Shows which are running, their ports, VRAM requirements, and categories."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="dragonsuite_vram",
            description="Show current GPU VRAM usage with a visual bar and GPU utilization %.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="dragonsuite_start",
            description=(
                "Start a Dragonsuite service using its configured launch_command. "
                "Output is logged to /tmp/dragonsuite_logs/<id>.log. "
                "For GPU services, warns if VRAM is already heavily used."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "Service ID to start",
                        "enum": ids_with_launch,
                    }
                },
                "required": ["service"],
            },
        ),
        Tool(
            name="dragonsuite_stop",
            description="Stop a running Dragonsuite service using its configured stop_command.",
            inputSchema={
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "Service ID to stop",
                        "enum": ids_with_stop,
                    }
                },
                "required": ["service"],
            },
        ),
        Tool(
            name="dragonsuite_logs",
            description=(
                "Tail a service's log file. Only available for services started via "
                "dragonsuite_start (logs written to /tmp/dragonsuite_logs/<id>.log). "
                "Returns an error if the service was started externally."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "Service ID",
                        "enum": ids,
                    },
                    "lines": {
                        "type": "integer",
                        "description": "Number of lines to return (default: 80)",
                        "default": 80,
                    },
                },
                "required": ["service"],
            },
        ),
        Tool(
            name="dragonsuite_check_port",
            description="Check what process (if any) is listening on a specific port.",
            inputSchema={
                "type": "object",
                "properties": {
                    "port": {
                        "type": "integer",
                        "description": "Port number to inspect",
                    }
                },
                "required": ["port"],
            },
        ),
        Tool(
            name="dragonsuite_kill_port",
            description=(
                "Kill whatever process is listening on a port. "
                "Useful for cleaning up orphaned services that won't stop normally."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "port": {
                        "type": "integer",
                        "description": "Port number to free up",
                    }
                },
                "required": ["port"],
            },
        ),
        Tool(
            name="dragonsuite_processes",
            description=(
                "Show all Python/GPU processes currently running: process name, PID, "
                "and which port they're using (if any). Good for spotting orphaned processes."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
    ]


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------

@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:

    # ---- status ------------------------------------------------------------
    if name == "dragonsuite_status":
        services = load_services()
        vram = get_vram()

        by_category: dict[str, list[str]] = {}
        for svc in services:
            cat = svc.get("category", "other")
            port = svc.get("port")
            always_on = svc.get("always_on", False)

            if always_on:
                indicator = "🔵"
                state = "always-on"
            elif port and check_port(port):
                indicator = "🟢"
                state = "running"
            elif port:
                indicator = "⚪"
                state = "stopped"
            else:
                # no port — check if stop_command exists (implies it's a background process)
                indicator = "⚪"
                state = "no-port"

            vram_info = f"  {svc['vram_gb']}GB VRAM" if svc.get("vram_gb") else ""
            port_info = f"  port {port}" if port else ""
            line = f"  {indicator} [{svc['id']}] {svc['name']} — {state}{port_info}{vram_info}"
            by_category.setdefault(cat, []).append(line)

        lines = []
        for cat, svc_lines in sorted(by_category.items()):
            lines.append(f"\n{cat.upper()}")
            lines.extend(svc_lines)

        if "error" not in vram:
            bar_len = 20
            filled = int(vram["used_percent"] / 100 * bar_len)
            bar = "█" * filled + "░" * (bar_len - filled)
            lines.append(
                f"\nGPU VRAM: [{bar}] {vram['used_percent']}%  "
                f"({vram['used_mb']:,}/{vram['total_mb']:,} MB)  "
                f"util {vram['gpu_util_percent']}%"
            )

        return [TextContent(type="text", text="\n".join(lines))]

    # ---- vram --------------------------------------------------------------
    elif name == "dragonsuite_vram":
        vram = get_vram()
        if "error" in vram:
            return [TextContent(type="text", text=f"Error: {vram['error']}")]

        bar_len = 30
        filled = int(vram["used_percent"] / 100 * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)

        text = (
            f"GPU VRAM\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Used:  {vram['used_mb']:,} MB\n"
            f"Free:  {vram['free_mb']:,} MB\n"
            f"Total: {vram['total_mb']:,} MB\n\n"
            f"[{bar}] {vram['used_percent']}%\n\n"
            f"GPU Utilization: {vram['gpu_util_percent']}%"
        )
        return [TextContent(type="text", text=text)]

    # ---- start -------------------------------------------------------------
    elif name == "dragonsuite_start":
        service_id = arguments.get("service", "")
        svc = find_service(service_id)
        if not svc:
            return [TextContent(type="text", text=f"Unknown service: {service_id}")]

        launch_cmd = svc.get("launch_command")
        if not launch_cmd:
            return [TextContent(type="text", text=f"{svc['name']} has no launch_command configured.")]

        port = svc.get("port")
        if port and check_port(port):
            return [TextContent(type="text", text=f"{svc['name']} is already running on port {port}.")]

        # VRAM warning for GPU services
        warning = ""
        vram_needed = svc.get("vram_gb", 0)
        if vram_needed:
            vram = get_vram()
            if "error" not in vram and vram["used_percent"] > 40:
                warning = (
                    f"⚠️  GPU is {vram['used_percent']}% full "
                    f"({vram['used_mb']:,}/{vram['total_mb']:,} MB). "
                    f"{svc['name']} needs ~{vram_needed}GB. "
                    "Stop other GPU services first if this fails.\n\n"
                )

        # Ensure log dir exists
        LOG_DIR.mkdir(exist_ok=True)
        log_file = LOG_DIR / f"{service_id}.log"

        # Launch with stdout+stderr → log file
        with open(log_file, "w") as lf:
            subprocess.Popen(
                launch_cmd,
                shell=True,
                cwd=str(BASE_DIR),
                stdout=lf,
                stderr=lf,
                start_new_session=True,
            )

        port_info = f"\nURL: http://192.168.7.226:{port}" if port else ""
        log_info = f"\nLog: {log_file}"
        return [TextContent(
            type="text",
            text=(
                f"{warning}Starting {svc['name']}...{port_info}{log_info}\n"
                "Models may take 30–120 seconds to load."
            )
        )]

    # ---- stop --------------------------------------------------------------
    elif name == "dragonsuite_stop":
        service_id = arguments.get("service", "")
        svc = find_service(service_id)
        if not svc:
            return [TextContent(type="text", text=f"Unknown service: {service_id}")]

        stop_cmd = svc.get("stop_command")
        if not stop_cmd:
            return [TextContent(type="text", text=f"{svc['name']} has no stop_command configured.")]

        port = svc.get("port")
        if port and not check_port(port):
            return [TextContent(type="text", text=f"{svc['name']} does not appear to be running (port {port} is free).")]

        result = subprocess.run(stop_cmd, shell=True, capture_output=True, text=True, cwd=str(BASE_DIR))
        msg = f"Stopped {svc['name']}."
        if result.returncode != 0 and result.stderr.strip():
            msg += f"\nstderr: {result.stderr.strip()}"
        return [TextContent(type="text", text=msg)]

    # ---- logs --------------------------------------------------------------
    elif name == "dragonsuite_logs":
        service_id = arguments.get("service", "")
        lines = int(arguments.get("lines", 80))
        svc = find_service(service_id)
        if not svc:
            return [TextContent(type="text", text=f"Unknown service: {service_id}")]

        log_file = LOG_DIR / f"{service_id}.log"
        if not log_file.exists():
            return [TextContent(
                type="text",
                text=(
                    f"No log file found at {log_file}.\n"
                    "Logs are only captured when a service is started via dragonsuite_start. "
                    "If you started this service from a terminal, logs went to that terminal's stdout."
                )
            )]

        result = subprocess.run(
            ["tail", "-n", str(lines), str(log_file)],
            capture_output=True, text=True,
        )
        content = result.stdout or "(empty log)"
        return [TextContent(type="text", text=f"=== {svc['name']} — last {lines} lines ===\n{content}")]

    # ---- check_port --------------------------------------------------------
    elif name == "dragonsuite_check_port":
        port = int(arguments.get("port", 0))
        if not port:
            return [TextContent(type="text", text="Invalid port number.")]

        result = subprocess.run(
            ["ss", "-tlnp", f"sport = :{port}"],
            capture_output=True, text=True, timeout=5,
        )
        lines = result.stdout.strip().split("\n")

        if len(lines) <= 1:
            # Check if anything matches via lsof as a fallback
            lsof = subprocess.run(
                ["lsof", "-i", f":{port}", "-n", "-P"],
                capture_output=True, text=True,
            )
            if lsof.stdout.strip():
                return [TextContent(type="text", text=f"Port {port} (lsof):\n{lsof.stdout.strip()}")]
            return [TextContent(type="text", text=f"Port {port}: nothing listening.")]

        # Find matching service in config
        svc_match = next((s for s in load_services() if s.get("port") == port), None)
        svc_label = f" → {svc_match['name']}" if svc_match else ""

        proc = process_on_port(port)
        proc_label = f"  process: {proc}" if proc else ""
        return [TextContent(
            type="text",
            text=f"Port {port}: OCCUPIED{svc_label}{proc_label}\n\n{result.stdout.strip()}"
        )]

    # ---- kill_port ---------------------------------------------------------
    elif name == "dragonsuite_kill_port":
        port = int(arguments.get("port", 0))
        if not port:
            return [TextContent(type="text", text="Invalid port number.")]

        if not check_port(port):
            return [TextContent(type="text", text=f"Port {port} is already free.")]

        proc = process_on_port(port)

        # fuser is the cleanest way to kill by port
        result = subprocess.run(
            ["fuser", "-k", f"{port}/tcp"],
            capture_output=True, text=True,
        )
        # brief pause then verify
        import time
        time.sleep(1)
        still_up = check_port(port)
        status = "still occupied ⚠️" if still_up else "now free ✓"
        return [TextContent(
            type="text",
            text=f"Killed {proc or 'process'} on port {port} — {status}"
        )]

    # ---- processes ---------------------------------------------------------
    elif name == "dragonsuite_processes":
        # Get all listening ports
        ss_result = subprocess.run(
            ["ss", "-tlnp"],
            capture_output=True, text=True,
        )

        # Get python/GPU processes
        ps_result = subprocess.run(
            ["ps", "aux", "--sort=-pid"],
            capture_output=True, text=True,
        )

        # Filter for relevant processes
        py_lines = []
        for line in ps_result.stdout.split("\n"):
            lower = line.lower()
            if any(k in lower for k in ["python", "gradio", "uvicorn", "node", "ollama", "vllm"]):
                # Trim overly long lines
                py_lines.append(line[:140])

        # Also show GPU compute processes via nvidia-smi
        gpu_result = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid,used_memory,process_name",
             "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10,
        )

        output = "=== Listening ports ===\n" + ss_result.stdout.strip()
        if py_lines:
            output += "\n\n=== Python/Node/Ollama processes ===\n" + "\n".join(py_lines[:40])
        if gpu_result.returncode == 0 and gpu_result.stdout.strip():
            output += "\n\n=== GPU compute processes ===\n" + gpu_result.stdout.strip()
        else:
            output += "\n\n=== GPU compute processes ===\n(none)"

        return [TextContent(type="text", text=output)]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
