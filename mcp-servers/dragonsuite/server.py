#!/usr/bin/env python3
"""
Dragonsuite MCP Server

Provides tools to manage Dragonsuite GPU services:
- List all services and their status
- Start/stop services
- Monitor VRAM usage
- View service logs
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

# Configuration
BASE_DIR = Path("/srv/containers/edq")
CONFIG_FILE = BASE_DIR / "config" / "dragonsuite.json"

# Service definitions with their systemd unit names and ports
SERVICES = {
    "dragonsuite": {
        "name": "Dragonsuite Dashboard",
        "port": 8100,
        "systemd": "dragonsuite.service",
        "gpu": False,
    },
    "dragonflux": {
        "name": "DragonFlux Klein",
        "port": 8001,
        "launcher": "scripts/start_flux2_klein.sh",
        "gpu": True,
        "vram": "~10GB",
    },
    "wan2gp": {
        "name": "Wan2GP Video",
        "port": 8002,
        "launcher": "scripts/start_wan2gp.sh",
        "gpu": True,
        "vram": "~12GB",
    },
    "fish-speech": {
        "name": "Fish Speech TTS",
        "port": 8003,
        "launcher": "scripts/start_fish_speech.sh",
        "gpu": True,
        "vram": "~12GB",
    },
    "heartmula": {
        "name": "HeartMuLa Music",
        "port": 8004,
        "launcher": "scripts/start_heartmula.sh",
        "gpu": True,
        "vram": "~12GB",
    },
    "sam2": {
        "name": "SAM 2.1 Segmentation",
        "port": 8005,
        "launcher": "scripts/start_sam2.sh",
        "gpu": True,
        "vram": "~6GB",
    },
    "sadtalker": {
        "name": "SadTalker",
        "port": 8006,
        "launcher": "scripts/start_sadtalker.sh",
        "gpu": True,
        "vram": "~4GB",
    },
    "hunyuan3d": {
        "name": "Hunyuan3D-2",
        "port": 8007,
        "launcher": "scripts/start_hunyuan3d.sh",
        "gpu": True,
        "vram": "~6-16GB",
    },
    "matanyone": {
        "name": "MatAnyone",
        "port": 8008,
        "launcher": "scripts/start_matanyone.sh",
        "gpu": True,
        "vram": "~9GB",
    },
    "qwen3-tts": {
        "name": "Qwen3-TTS",
        "port": 8009,
        "launcher": "scripts/start_qwen3_tts.sh",
        "gpu": True,
        "vram": "~6-8GB",
    },
    "realesrgan": {
        "name": "Real-ESRGAN",
        "port": 8010,
        "launcher": "scripts/start_realesrgan.sh",
        "gpu": True,
        "vram": "~4GB",
    },
    "zimage": {
        "name": "Z-Image Base",
        "port": 8011,
        "launcher": "scripts/start_zimage.sh",
        "gpu": True,
        "vram": "~13-14GB",
    },
    "rembg": {
        "name": "Rembg",
        "port": 8012,
        "launcher": "scripts/start_rembg.sh",
        "gpu": True,
        "vram": "~2GB",
    },
    "qwen-layered": {
        "name": "Qwen-Image-Layered",
        "port": 8013,
        "launcher": "scripts/start_qwen_image_layered.sh",
        "gpu": True,
        "vram": "~14-16GB",
    },
    "remotion": {
        "name": "Remotion Studio",
        "port": 3000,
        "systemd": "remotion-studio.service",
        "gpu": False,
    },
}

server = Server("dragonsuite")


def check_port(port: int) -> bool:
    """Check if a port is in use (service running)."""
    try:
        result = subprocess.run(
            ["ss", "-tlnp", f"sport = :{port}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return bool(result.stdout.strip().split("\n")[1:])
    except Exception:
        return False


def get_vram_usage() -> dict:
    """Get current VRAM usage from nvidia-smi."""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.used,memory.total,memory.free,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(",")
            return {
                "used_mb": int(parts[0].strip()),
                "total_mb": int(parts[1].strip()),
                "free_mb": int(parts[2].strip()),
                "gpu_util_percent": int(parts[3].strip()),
                "used_percent": round(int(parts[0].strip()) / int(parts[1].strip()) * 100, 1),
            }
    except Exception as e:
        return {"error": str(e)}
    return {"error": "nvidia-smi failed"}


def get_process_on_port(port: int) -> str | None:
    """Get the process name using a specific port."""
    try:
        result = subprocess.run(
            ["ss", "-tlnp", f"sport = :{port}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        output = result.stdout
        # Parse process name from ss output
        match = re.search(r'users:\(\("([^"]+)"', output)
        if match:
            return match.group(1)
    except Exception:
        pass
    return None


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available Dragonsuite tools."""
    return [
        Tool(
            name="dragonsuite_status",
            description="Get status of all Dragonsuite services. Shows which are running, their ports, and VRAM requirements.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="dragonsuite_vram",
            description="Get current GPU VRAM usage. Shows used/total memory and GPU utilization.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="dragonsuite_start",
            description="Start a Dragonsuite service. Only one GPU service should run at a time due to VRAM limits.",
            inputSchema={
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "Service ID to start (e.g., 'dragonflux', 'wan2gp', 'fish-speech')",
                        "enum": list(SERVICES.keys()),
                    }
                },
                "required": ["service"],
            },
        ),
        Tool(
            name="dragonsuite_stop",
            description="Stop a running Dragonsuite service.",
            inputSchema={
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "Service ID to stop",
                        "enum": list(SERVICES.keys()),
                    }
                },
                "required": ["service"],
            },
        ),
        Tool(
            name="dragonsuite_logs",
            description="Get recent logs from a service (last 50 lines).",
            inputSchema={
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "Service ID to get logs for",
                        "enum": list(SERVICES.keys()),
                    },
                    "lines": {
                        "type": "integer",
                        "description": "Number of log lines to retrieve (default: 50)",
                        "default": 50,
                    },
                },
                "required": ["service"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""

    if name == "dragonsuite_status":
        status_list = []
        vram = get_vram_usage()

        for svc_id, svc in SERVICES.items():
            running = check_port(svc["port"])
            status = "running" if running else "stopped"
            emoji = "🟢" if running else "⚪"
            gpu_info = f" (GPU: {svc.get('vram', 'N/A')})" if svc.get("gpu") else ""

            status_list.append(
                f"{emoji} {svc['name']}: {status} (port {svc['port']}){gpu_info}"
            )

        vram_info = ""
        if "error" not in vram:
            vram_info = f"\n\nGPU VRAM: {vram['used_mb']}MB / {vram['total_mb']}MB ({vram['used_percent']}% used)"
            vram_info += f"\nGPU Utilization: {vram['gpu_util_percent']}%"

        return [TextContent(type="text", text="\n".join(status_list) + vram_info)]

    elif name == "dragonsuite_vram":
        vram = get_vram_usage()
        if "error" in vram:
            return [TextContent(type="text", text=f"Error: {vram['error']}")]

        bar_len = 20
        filled = int(vram["used_percent"] / 100 * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)

        text = f"""GPU VRAM Usage
━━━━━━━━━━━━━━━━━━━━━━━━
Used:  {vram['used_mb']:,} MB
Free:  {vram['free_mb']:,} MB
Total: {vram['total_mb']:,} MB

[{bar}] {vram['used_percent']}%

GPU Utilization: {vram['gpu_util_percent']}%"""

        return [TextContent(type="text", text=text)]

    elif name == "dragonsuite_start":
        service_id = arguments.get("service")
        if service_id not in SERVICES:
            return [TextContent(type="text", text=f"Unknown service: {service_id}")]

        svc = SERVICES[service_id]

        # Check if already running
        if check_port(svc["port"]):
            return [TextContent(type="text", text=f"{svc['name']} is already running on port {svc['port']}")]

        # For GPU services, warn about VRAM
        if svc.get("gpu"):
            vram = get_vram_usage()
            if "error" not in vram and vram["used_percent"] > 50:
                warning = f"Warning: GPU already using {vram['used_percent']}% VRAM. "
                warning += "Consider stopping other GPU services first.\n\n"
            else:
                warning = ""
        else:
            warning = ""

        # Start the service
        if "systemd" in svc:
            # Use systemctl for systemd services
            result = subprocess.run(
                ["systemctl", "--user", "start", svc["systemd"]],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return [TextContent(type="text", text=f"{warning}Started {svc['name']} via systemd")]
            else:
                return [TextContent(type="text", text=f"Failed to start: {result.stderr}")]
        else:
            # Use launcher script (run in background)
            launcher = BASE_DIR / svc["launcher"]
            if not launcher.exists():
                return [TextContent(type="text", text=f"Launcher not found: {launcher}")]

            # Start in background
            subprocess.Popen(
                ["bash", str(launcher)],
                cwd=str(BASE_DIR),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

            return [TextContent(
                type="text",
                text=f"{warning}Starting {svc['name']}...\nURL: http://192.168.7.226:{svc['port']}\n\nNote: May take 30-60 seconds to load models."
            )]

    elif name == "dragonsuite_stop":
        service_id = arguments.get("service")
        if service_id not in SERVICES:
            return [TextContent(type="text", text=f"Unknown service: {service_id}")]

        svc = SERVICES[service_id]

        if not check_port(svc["port"]):
            return [TextContent(type="text", text=f"{svc['name']} is not running")]

        if "systemd" in svc:
            result = subprocess.run(
                ["systemctl", "--user", "stop", svc["systemd"]],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return [TextContent(type="text", text=f"Stopped {svc['name']}")]
            else:
                return [TextContent(type="text", text=f"Failed to stop: {result.stderr}")]
        else:
            # Kill process on port
            proc_name = get_process_on_port(svc["port"])
            subprocess.run(
                ["pkill", "-f", f":{svc['port']}"],
                capture_output=True,
            )
            # Also try killing by launcher script name
            if "launcher" in svc:
                script_name = Path(svc["launcher"]).stem
                subprocess.run(["pkill", "-f", script_name], capture_output=True)

            return [TextContent(type="text", text=f"Stopped {svc['name']} (was: {proc_name or 'unknown'})")]

    elif name == "dragonsuite_logs":
        service_id = arguments.get("service")
        lines = arguments.get("lines", 50)

        if service_id not in SERVICES:
            return [TextContent(type="text", text=f"Unknown service: {service_id}")]

        svc = SERVICES[service_id]

        if "systemd" in svc:
            result = subprocess.run(
                ["journalctl", "--user", "-u", svc["systemd"], "-n", str(lines), "--no-pager"],
                capture_output=True,
                text=True,
            )
            return [TextContent(type="text", text=result.stdout or result.stderr or "No logs found")]
        else:
            return [TextContent(
                type="text",
                text=f"Logs for non-systemd services not yet implemented. Service {svc['name']} uses launcher script."
            )]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
