#!/usr/bin/env python3
"""
Dragonclawd — Personal AI Agent (Telegram Bot)
Powered by Claude Sonnet + Dragonsuite integration + MCP servers

Setup:
  1. Get bot token from @BotFather in Telegram
  2. Get your user ID from @userinfobot
  3. Add to /srv/containers/edq/.env:
       TELEGRAM_BOT_TOKEN=<token>
       TELEGRAM_ALLOWED_USERS=<comma-separated user IDs>
  4. bash scripts/start_dragonclawd.sh
"""

import os
import sys
import json
import glob
import shutil
import asyncio
import logging
import subprocess
from collections import deque
from contextlib import AsyncExitStack
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import requests
from dotenv import load_dotenv
from telegram import Update, BotCommand
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters
)
import anthropic

sys.path.insert(0, '/srv/containers/edq')
from scripts import provider_models

# ── Environment ──────────────────────────────────────────────────────────────
load_dotenv("/srv/containers/edq/.env")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ALLOWED_USERS_RAW = os.getenv("TELEGRAM_ALLOWED_USERS", "")
ALLOWED_USERS = set(uid.strip() for uid in ALLOWED_USERS_RAW.split(",") if uid.strip())
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

def anthropic_model(task='chat'):
    preferred = os.environ.get('ANTHROPIC_MODEL')
    return provider_models.resolve_model('anthropic', task, preferred=preferred).get('model') or 'claude-sonnet-4-6'


DRAGONSUITE_API = "http://127.0.0.1:8100/api"
OLLAMA_API = "http://127.0.0.1:11434"
BASE_DIR = Path("/srv/containers/edq")
AI_GEN_DIR = Path("/home/edq/ai_generated")

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)

# ── Conversation history (per user, last 20 messages) ────────────────────────
conversation_history: dict[str, deque] = {}

def get_history(user_id: str) -> list:
    if user_id not in conversation_history:
        conversation_history[user_id] = deque(maxlen=20)
    return list(conversation_history[user_id])

def add_to_history(user_id: str, role: str, content: Any):
    if user_id not in conversation_history:
        conversation_history[user_id] = deque(maxlen=20)
    conversation_history[user_id].append({"role": role, "content": content})

def clear_history(user_id: str):
    conversation_history[user_id] = deque(maxlen=20)

# ── File helpers ───────────────────────────────────────────────────────────────

def copy_to_ai_generated(src_path: str, service: str) -> Optional[Path]:
    """Copy a temp-generated file to /home/edq/ai_generated/<service>/."""
    src = Path(src_path)
    if not src.exists():
        log.warning(f"Source file not found for copy: {src_path}")
        return None
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest_dir = AI_GEN_DIR / service
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{timestamp}{src.suffix}"
    shutil.copy2(src, dest)
    log.info(f"Copied {src} → {dest}")
    return dest

# ── MCP Manager ───────────────────────────────────────────────────────────────

class MCPManager:
    """Manages connections to stdio MCP servers."""

    # Servers to connect on startup — subset of .mcp.json that are useful for the bot
    SERVER_CONFIGS = {
        "filesystem": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem",
                     "/srv/containers/edq", "/home/edq/ai_generated", "/home/edq/knowledge-base"],
        },
        "obsidian": {
            "command": "npx",
            "args": ["-y", "obsidian-mcp", "/home/edq/knowledge-base"],
        },
    }

    def __init__(self):
        self.exit_stack = AsyncExitStack()
        self.sessions: dict[str, Any] = {}   # name -> ClientSession
        self.server_tools: dict[str, list] = {}  # name -> [Tool, ...]
        self._ready = False

    async def start(self):
        """Connect to all configured MCP servers."""
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError:
            log.warning("mcp library not installed — MCP servers unavailable")
            return

        for name, cfg in self.SERVER_CONFIGS.items():
            try:
                params = StdioServerParameters(
                    command=cfg["command"],
                    args=cfg["args"],
                    env=cfg.get("env"),
                )
                read, write = await self.exit_stack.enter_async_context(
                    stdio_client(params)
                )
                session = await self.exit_stack.enter_async_context(
                    ClientSession(read, write)
                )
                await session.initialize()
                result = await session.list_tools()
                self.sessions[name] = session
                self.server_tools[name] = result.tools
                log.info(f"MCP server '{name}' connected — {len(result.tools)} tools")
            except Exception as e:
                log.warning(f"MCP server '{name}' failed to start: {e}")

        self._ready = True

    async def stop(self):
        await self.exit_stack.aclose()

    def get_anthropic_tools(self) -> list[dict]:
        """Return all MCP tools in Anthropic tool format, prefixed with mcp__<server>__."""
        tools = []
        for server_name, server_tools in self.server_tools.items():
            for tool in server_tools:
                tools.append({
                    "name": f"mcp__{server_name}__{tool.name}",
                    "description": f"[{server_name}] {tool.description or ''}",
                    "input_schema": tool.inputSchema or {"type": "object", "properties": {}, "required": []},
                })
        return tools

    async def call_tool(self, prefixed_name: str, inputs: dict) -> str:
        """Call an MCP tool by its prefixed name (mcp__<server>__<tool>)."""
        try:
            _, server_name, tool_name = prefixed_name.split("__", 2)
        except ValueError:
            return f"Invalid MCP tool name: {prefixed_name}"

        if server_name not in self.sessions:
            return f"MCP server '{server_name}' is not connected."

        try:
            session = self.sessions[server_name]
            result = await session.call_tool(tool_name, inputs)
            parts = []
            for content in result.content:
                if hasattr(content, "text"):
                    parts.append(content.text)
                elif hasattr(content, "data"):
                    parts.append(f"[binary: {len(content.data)} bytes]")
            return "\n".join(parts) or "(empty result)"
        except Exception as e:
            return f"MCP tool error ({prefixed_name}): {e}"


# Global MCP manager — started in main()
mcp_manager = MCPManager()

# ── Native tool definitions (Anthropic format) ────────────────────────────────
NATIVE_TOOLS = [
    {
        "name": "get_status",
        "description": "Get status of all Dragonsuite services (running/stopped) and current GPU/system stats. Call this when asked about what's running, GPU usage, or service availability.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "start_service",
        "description": "Start a Dragonsuite service by its ID. Check get_status first to see available service IDs and whether GPU services may conflict.",
        "input_schema": {
            "type": "object",
            "properties": {
                "service_id": {
                    "type": "string",
                    "description": "Service ID from dragonsuite config (e.g. 'dragonflux-klein', 'zimage-base', 'wan2gp', 'qwen3-tts')"
                }
            },
            "required": ["service_id"]
        }
    },
    {
        "name": "stop_service",
        "description": "Stop a running Dragonsuite service by its ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "service_id": {
                    "type": "string",
                    "description": "Service ID to stop"
                }
            },
            "required": ["service_id"]
        }
    },
    {
        "name": "get_gpu_stats",
        "description": "Get detailed GPU VRAM usage, temperature, and utilization from the RTX 5070 Ti.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "run_shell",
        "description": "Run a safe, read-only shell command on udragon. Only informational commands are permitted (ls, df, free, ps, nvidia-smi, etc). Use this to check disk space, running processes, file listings, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to run (read-only/safe commands only)"
                }
            },
            "required": ["command"]
        }
    },
    {
        "name": "list_files",
        "description": "List files in a directory under /home/edq/ai_generated or /srv/containers/edq. Supports glob patterns.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path or glob pattern (e.g. '/home/edq/ai_generated/*.png')"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "read_file",
        "description": "Read the contents of a text file. Size-limited to 50KB. Useful for reading logs, config files, or generated text.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path to the file"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "generate_image",
        "description": (
            "Generate an image using a local AI service. Automatically picks the best available backend:\n"
            "- DragonFlux Klein (port 8001): FLUX.2-klein, very fast, 4-step, great for quick results\n"
            "- Z-Image Base (port 8011): Alibaba 6B model, slower but excellent text rendering and photorealism\n"
            "Check get_status() if unsure which is running. Image is sent back directly in chat."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Image generation prompt"
                },
                "backend": {
                    "type": "string",
                    "description": "'auto' (default), 'dragonflux-klein', or 'zimage-base'",
                    "default": "auto"
                },
                "aspect_ratio": {
                    "type": "string",
                    "description": "Aspect ratio: '1:1', '16:9', '9:16', '4:3', '3:4'. Default: '1:1'",
                    "default": "1:1"
                },
                "negative_prompt": {
                    "type": "string",
                    "description": "What to avoid in the image (Z-Image Base only). Optional.",
                    "default": ""
                },
                "quality": {
                    "type": "string",
                    "description": "'fast' (Turbo/4-step) or 'quality' (Base/30-step). Default: 'fast'",
                    "default": "fast"
                }
            },
            "required": ["prompt"]
        }
    },
    {
        "name": "generate_tts",
        "description": "Generate text-to-speech audio using Qwen3-TTS (port 8009). The service must be running first. Audio is sent back directly in chat.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to convert to speech"
                },
                "voice": {
                    "type": "string",
                    "description": "Voice style description (e.g. 'calm female narrator', 'energetic male'). Optional.",
                    "default": "natural"
                }
            },
            "required": ["text"]
        }
    },
]

# ── Tool implementations ───────────────────────────────────────────────────────

def tool_get_status() -> str:
    try:
        resp = requests.get(f"{DRAGONSUITE_API}/status", timeout=5)
        data = resp.json()
        services = data.get("services", [])
        running = [s for s in services if s.get("running")]
        stopped = [s for s in services if not s.get("running")]

        lines = [f"**Dragonsuite Status** ({len(running)} running / {len(services)} total)\n"]

        if running:
            lines.append("🟢 Running:")
            for s in running:
                port_info = f" (port {s['port']})" if s.get("port") else ""
                lines.append(f"  • {s['name']}{port_info}")

        if stopped:
            lines.append("\n⚫ Stopped (sample):")
            for s in stopped[:8]:
                lines.append(f"  • {s['name']}")
            if len(stopped) > 8:
                lines.append(f"  ... and {len(stopped) - 8} more")

        # GPU stats inline
        try:
            gpu = requests.get(f"{DRAGONSUITE_API}/gpu-stats", timeout=3).json()
            vram_used = gpu.get("vram_used_mb", 0)
            vram_total = gpu.get("vram_total_mb", 16384)
            utilization = gpu.get("gpu_utilization", 0)
            temp = gpu.get("gpu_temp", 0)
            lines.append(f"\n🎮 GPU: {vram_used}MB / {vram_total}MB VRAM ({utilization}% util, {temp}°C)")
        except Exception:
            pass

        return "\n".join(lines)
    except Exception as e:
        return f"Error getting status: {e}"


def tool_start_service(service_id: str) -> str:
    try:
        resp = requests.post(f"{DRAGONSUITE_API}/start/{service_id}", timeout=10)
        data = resp.json()
        return f"✅ {data.get('message', 'Service started')}"
    except Exception as e:
        return f"Error starting {service_id}: {e}"


def tool_stop_service(service_id: str) -> str:
    try:
        resp = requests.post(f"{DRAGONSUITE_API}/stop/{service_id}", timeout=10)
        data = resp.json()
        return f"⛔ {data.get('message', 'Service stopped')}"
    except Exception as e:
        return f"Error stopping {service_id}: {e}"


def tool_get_gpu_stats() -> str:
    try:
        gpu = requests.get(f"{DRAGONSUITE_API}/gpu-stats", timeout=5).json()
        vram_used = gpu.get("vram_used_mb", 0)
        vram_total = gpu.get("vram_total_mb", 16384)
        vram_free = vram_total - vram_used
        utilization = gpu.get("gpu_utilization", 0)
        temp = gpu.get("gpu_temp", 0)
        return (
            f"RTX 5070 Ti GPU Stats:\n"
            f"  VRAM: {vram_used}MB used / {vram_total}MB total ({vram_free}MB free)\n"
            f"  Utilization: {utilization}%\n"
            f"  Temperature: {temp}°C"
        )
    except Exception as e:
        return f"Error getting GPU stats: {e}"


# Safe shell command allowlist
SHELL_SAFE_PREFIXES = (
    "ls", "pwd", "df ", "df\n", "free", "uptime", "date",
    "nvidia-smi", "ps aux", "ps -", "cat /proc/",
    "du -sh", "du -h", "grep ", "find /home/edq/ai_generated",
    "find /srv/containers/edq/logs", "tail ", "head ",
    "wc ", "echo ", "which ", "python3 --version", "pip list",
    "uname", "hostname", "whoami", "id ",
)

def tool_run_shell(command: str) -> str:
    cmd_stripped = command.strip()
    if not any(cmd_stripped.startswith(p) for p in SHELL_SAFE_PREFIXES):
        return (
            f"Command not in allowlist: '{cmd_stripped[:60]}'\n"
            "Allowed: ls, pwd, df, free, uptime, nvidia-smi, ps, grep, find (ai_generated only), tail, head, du, etc."
        )
    try:
        result = subprocess.run(
            cmd_stripped, shell=True, capture_output=True,
            text=True, timeout=10
        )
        output = result.stdout or result.stderr
        return output[:3000] if output else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Command timed out (10s limit)"
    except Exception as e:
        return f"Error: {e}"


ALLOWED_LIST_PATHS = (
    "/home/edq/ai_generated",
    "/srv/containers/edq/logs",
    "/srv/containers/edq/config",
    "/tmp",
)

def tool_list_files(path: str) -> str:
    real_path = os.path.realpath(path.split("*")[0])
    if not any(real_path.startswith(p) for p in ALLOWED_LIST_PATHS):
        return f"Access denied: only allowed in {', '.join(ALLOWED_LIST_PATHS)}"
    try:
        if "*" in path or "?" in path:
            matches = glob.glob(path, recursive=True)
            matches = sorted(matches)[:50]
            if not matches:
                return f"No files matching: {path}"
            return "\n".join(matches)
        else:
            p = Path(path)
            if p.is_file():
                stat = p.stat()
                return f"{path} ({stat.st_size} bytes)"
            if not p.exists():
                return f"Path does not exist: {path}"
            entries = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name))
            lines = []
            for entry in entries[:50]:
                stat = entry.stat()
                size = f"{stat.st_size:,}B" if entry.is_file() else "dir"
                lines.append(f"  {'📄' if entry.is_file() else '📁'} {entry.name} ({size})")
            if len(list(p.iterdir())) > 50:
                lines.append(f"  ... (truncated, >50 entries)")
            return f"{path}:\n" + "\n".join(lines) if lines else f"{path}: (empty)"
    except Exception as e:
        return f"Error listing {path}: {e}"


ALLOWED_READ_PATHS = (
    "/home/edq/ai_generated",
    "/srv/containers/edq/logs",
    "/srv/containers/edq/config",
    "/srv/containers/edq/docs",
    "/tmp",
    "/home/edq/.claude/projects/-srv-containers-edq/memory",
)
MAX_READ_BYTES = 50_000

def tool_read_file(path: str) -> str:
    real_path = os.path.realpath(path)
    if not any(real_path.startswith(p) for p in ALLOWED_READ_PATHS):
        return f"Access denied: {path}"
    try:
        p = Path(real_path)
        if not p.exists():
            return f"File not found: {path}"
        if not p.is_file():
            return f"Not a file: {path}"
        size = p.stat().st_size
        if size > MAX_READ_BYTES:
            return f"File too large ({size:,} bytes). Max: {MAX_READ_BYTES:,} bytes."
        return p.read_text(errors="replace")
    except Exception as e:
        return f"Error reading {path}: {e}"


# Image size map — aspect ratio → (width, height)
ASPECT_TO_SIZE = {
    "1:1":  (1024, 1024),
    "16:9": (1280, 720),
    "9:16": (720, 1280),
    "4:3":  (1024, 768),
    "3:4":  (768, 1024),
}

def _get_running_service_ids() -> set[str]:
    """Return the set of running service IDs from Dragonsuite."""
    try:
        resp = requests.get(f"{DRAGONSUITE_API}/status", timeout=5)
        return {s["id"] for s in resp.json().get("services", []) if s.get("running")}
    except Exception:
        return set()


def _generate_via_klein(prompt: str, aspect_ratio: str) -> tuple[str, Optional[Path]]:
    """Generate image with DragonFlux Klein (port 8001). Returns (message, path_or_None)."""
    w, h = ASPECT_TO_SIZE.get(aspect_ratio, (1024, 1024))
    try:
        from gradio_client import Client
        client = Client("http://127.0.0.1:8001/", verbose=False)
        result = client.predict(
            prompt=prompt,
            model_variant="FLUX.2-klein-4B (Recommended) - ~12GB",
            aspect_ratio=aspect_ratio,
            width=w,
            height=h,
            guidance_scale=1.0,
            num_inference_steps=4,
            seed=-1,
            api_name="/generate_image"
        )
        tmp_path = result[0] if isinstance(result, (list, tuple)) else str(result)
        dest = copy_to_ai_generated(tmp_path, "dragonflux-klein")
        if dest:
            return (f"✅ Image generated via DragonFlux Klein\nSaved: {dest}", dest)
        return (f"✅ Image generated (temp): {tmp_path}", Path(tmp_path))
    except Exception as e:
        return (f"DragonFlux Klein error: {e}", None)


def _generate_via_zimage(
    prompt: str,
    aspect_ratio: str,
    negative_prompt: str = "",
    quality: str = "fast",
) -> tuple[str, Optional[Path]]:
    """Generate image with Z-Image Base (port 8011). Returns (message, path_or_None)."""
    w, h = ASPECT_TO_SIZE.get(aspect_ratio, (1024, 1024))
    model_type = "Base" if quality == "quality" else "Turbo"
    guidance = 7.0 if model_type == "Base" else 1.0
    steps = 30 if model_type == "Base" else 8
    try:
        from gradio_client import Client
        client = Client("http://127.0.0.1:8011/", verbose=False)
        result = client.predict(
            prompt,
            negative_prompt,
            model_type,
            "None",       # controlnet_condition
            None,         # control_image
            1.0,          # controlnet_scale
            aspect_ratio,
            w,
            h,
            guidance,
            steps,
            -1,           # seed
            False,        # fast_mode (LoRA shortcut)
            None,         # lora_dropdown
            1.0,          # lora_scale
            api_name="/generate_image"
        )
        tmp_path = result[0] if isinstance(result, (list, tuple)) else str(result)
        dest = copy_to_ai_generated(tmp_path, "zimage-base")
        if dest:
            return (f"✅ Image generated via Z-Image {model_type}\nSaved: {dest}", dest)
        return (f"✅ Image generated (temp): {tmp_path}", Path(tmp_path))
    except Exception as e:
        return (f"Z-Image error: {e}", None)


def tool_generate_image(
    prompt: str,
    backend: str = "auto",
    aspect_ratio: str = "1:1",
    negative_prompt: str = "",
    quality: str = "fast",
) -> tuple[str, Optional[Path]]:
    running = _get_running_service_ids()

    if backend == "auto":
        if "dragonflux-klein" in running:
            backend = "dragonflux-klein"
        elif "zimage-base" in running:
            backend = "zimage-base"
        else:
            return (
                "⚠️ No image generation service is running.\n"
                "Start one: `start_service('dragonflux-klein')` (fast) or `start_service('zimage-base')` (quality)",
                None
            )

    if backend == "dragonflux-klein":
        if "dragonflux-klein" not in running:
            return ("DragonFlux Klein is not running. Start it with start_service('dragonflux-klein').", None)
        return _generate_via_klein(prompt, aspect_ratio)

    if backend == "zimage-base":
        if "zimage-base" not in running:
            return ("Z-Image Base is not running. Start it with start_service('zimage-base').", None)
        return _generate_via_zimage(prompt, aspect_ratio, negative_prompt, quality)

    return (f"Unknown backend: {backend}. Use 'auto', 'dragonflux-klein', or 'zimage-base'.", None)


def tool_generate_tts(text: str, voice: str = "natural") -> tuple[str, Optional[Path]]:
    running = _get_running_service_ids()
    if "qwen3-tts" not in running:
        return ("Qwen3-TTS is not running. Start it with start_service('qwen3-tts').", None)
    try:
        from gradio_client import Client
        client = Client("http://127.0.0.1:8009/", verbose=False)
        result = client.predict(
            text=text,
            voice=voice,
            api_name="/generate"
        )
        tmp_path = result[0] if isinstance(result, (list, tuple)) else str(result)
        dest = copy_to_ai_generated(tmp_path, "qwen3-tts")
        if dest:
            return (f"✅ Audio generated\nSaved: {dest}", dest)
        return (f"✅ Audio generated (temp): {tmp_path}", Path(tmp_path))
    except Exception as e:
        return (f"Error generating TTS: {e}", None)


# ── Tool dispatch (returns text + optional attachment) ─────────────────────────

async def dispatch_tool(name: str, inputs: dict) -> tuple[str, Optional[Path]]:
    """
    Dispatch a tool call. Returns (result_text, attachment_path_or_None).
    MCP tools are dispatched via mcp_manager; native tools run in a thread.
    """
    loop = asyncio.get_event_loop()
    no_attach: Optional[Path] = None

    # MCP tools
    if name.startswith("mcp__"):
        result_text = await mcp_manager.call_tool(name, inputs)
        return (result_text, no_attach)

    # Native tools
    def run_native():
        try:
            if name == "get_status":
                return (tool_get_status(), no_attach)
            elif name == "start_service":
                return (tool_start_service(inputs["service_id"]), no_attach)
            elif name == "stop_service":
                return (tool_stop_service(inputs["service_id"]), no_attach)
            elif name == "get_gpu_stats":
                return (tool_get_gpu_stats(), no_attach)
            elif name == "run_shell":
                return (tool_run_shell(inputs["command"]), no_attach)
            elif name == "list_files":
                return (tool_list_files(inputs["path"]), no_attach)
            elif name == "read_file":
                return (tool_read_file(inputs["path"]), no_attach)
            elif name == "generate_image":
                return tool_generate_image(
                    inputs["prompt"],
                    inputs.get("backend", "auto"),
                    inputs.get("aspect_ratio", "1:1"),
                    inputs.get("negative_prompt", ""),
                    inputs.get("quality", "fast"),
                )
            elif name == "generate_tts":
                return tool_generate_tts(inputs["text"], inputs.get("voice", "natural"))
            else:
                return (f"Unknown tool: {name}", no_attach)
        except Exception as e:
            return (f"Tool error ({name}): {e}", no_attach)

    return await loop.run_in_executor(None, run_native)


# ── System prompt ─────────────────────────────────────────────────────────────

def build_system_prompt() -> str:
    mcp_section = ""
    if mcp_manager.sessions:
        connected = ", ".join(mcp_manager.sessions.keys())
        mcp_section = f"\nMCP servers connected: {connected} (tools prefixed with mcp__<server>__)"
    else:
        mcp_section = "\nMCP servers: not connected (starting up or unavailable)"

    return f"""You are Dragonclawd, a personal AI assistant running on udragon — an Ubuntu server with an RTX 5070 Ti GPU (16GB VRAM).

Your owner is a developer who uses this machine for AI experimentation. You have access to tools to:
- Check and control 35+ Dragonsuite AI services (image gen, video, TTS, vision, etc.)
- Monitor GPU/system stats
- Run safe shell commands
- Browse and read files in the AI output directory
- Generate images via **either** DragonFlux Klein (fast, FLUX.2) or Z-Image Base (quality, Alibaba 6B)
- Generate speech audio via Qwen3-TTS
- Access the filesystem and Obsidian knowledge base via MCP tools
{mcp_section}

Image generation notes:
- Use `generate_image` with backend='auto' to pick whichever service is running
- DragonFlux Klein (8001): ~12GB VRAM, 4-step, very fast
- Z-Image Base (8011): ~8GB VRAM, 30/8-step, better text/realism, supports negative prompts
- Generated images are saved to /home/edq/ai_generated/<service>/ and sent back as photos in chat

Personality: Helpful, concise, technically savvy. Use markdown formatting. Keep responses brief for chat — don't over-explain.

Key facts:
- All AI services are at ports 8001-8033, Dragonsuite dashboard at 8100
- Generated files go to /home/edq/ai_generated/<service>/
- Only one GPU-heavy service can run at a time (16GB VRAM limit)
- When starting GPU services, check GPU stats and warn if VRAM is tight
- Service IDs use kebab-case: dragonflux-klein, zimage-base, wan2gp, qwen3-tts, fish-speech, etc.

When unsure about a service ID, call get_status() first to see the full list."""


# ── Agent loop ────────────────────────────────────────────────────────────────

async def run_agent_loop(user_message: str, user_id: str) -> tuple[str, list[Path]]:
    """
    Run the agent loop. Returns (reply_text, attachment_paths).
    attachment_paths contains any generated files to send back to the user.
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    history = get_history(user_id)
    messages = history + [{"role": "user", "content": user_message}]

    # Build tool list: native + MCP
    all_tools = NATIVE_TOOLS + mcp_manager.get_anthropic_tools()

    MAX_TOOL_ROUNDS = 8
    tool_rounds = 0
    attachments: list[Path] = []

    while tool_rounds < MAX_TOOL_ROUNDS:
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: client.messages.create(
                model=anthropic_model(),
                max_tokens=2048,
                system=build_system_prompt(),
                tools=all_tools,
                messages=messages,
            )
        )

        content_blocks = response.content

        if response.stop_reason == "end_turn":
            text = next(
                (b.text for b in content_blocks if hasattr(b, "text")),
                "(no response)"
            )
            add_to_history(user_id, "user", user_message)
            add_to_history(user_id, "assistant", text)
            return (text, attachments)

        elif response.stop_reason == "tool_use":
            tool_rounds += 1
            tool_results = []
            for block in content_blocks:
                if block.type == "tool_use":
                    log.info(f"Tool call: {block.name}({block.input})")
                    result_text, attachment = await dispatch_tool(block.name, block.input)
                    log.info(f"Tool result: {result_text[:200]}")
                    if attachment and attachment.exists():
                        attachments.append(attachment)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_text,
                    })

            messages.append({"role": "assistant", "content": content_blocks})
            messages.append({"role": "user", "content": tool_results})

        else:
            text = next(
                (b.text for b in content_blocks if hasattr(b, "text")),
                f"(stopped: {response.stop_reason})"
            )
            return (text, attachments)

    return ("⚠️ Too many tool rounds — something went wrong. Try rephrasing.", attachments)


# ── Telegram handlers ─────────────────────────────────────────────────────────

def auth_check(update: Update) -> bool:
    if not ALLOWED_USERS:
        log.warning("TELEGRAM_ALLOWED_USERS not set — all users blocked!")
        return False
    user = update.effective_user
    user_id = str(user.id)
    username = (user.username or "").lower()
    allowed_lower = {u.lower() for u in ALLOWED_USERS}
    return user_id in allowed_lower or username in allowed_lower


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth_check(update):
        await update.message.reply_text("🚫 Not authorized.")
        return

    mcp_status = "✅ Connected" if mcp_manager.sessions else "⚠️ Not connected"
    mcp_servers = ", ".join(mcp_manager.sessions.keys()) if mcp_manager.sessions else "none"

    await update.message.reply_text(
        "🐉 *Dragonclawd* online!\n\n"
        "I'm your personal AI agent for udragon. I can:\n"
        "• Check and control Dragonsuite services\n"
        "• Monitor GPU and system stats\n"
        "• Generate images (Klein or Z-Image, auto-detected)\n"
        "• Generate speech audio via Qwen3-TTS\n"
        "• Browse your AI output files\n"
        f"• MCP servers: {mcp_status} ({mcp_servers})\n\n"
        "Just ask me anything in natural language.\n\n"
        "Commands: /status /mcp /clear /help",
        parse_mode=ParseMode.MARKDOWN
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth_check(update):
        await update.message.reply_text("🚫 Not authorized.")
        return
    await update.message.reply_text("Checking...")
    status = tool_get_status()
    await update.message.reply_text(status, parse_mode=ParseMode.MARKDOWN)


async def cmd_mcp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth_check(update):
        await update.message.reply_text("🚫 Not authorized.")
        return

    if not mcp_manager.sessions:
        await update.message.reply_text("⚠️ No MCP servers connected.")
        return

    lines = ["🔌 *MCP Servers*\n"]
    for server_name, tools in mcp_manager.server_tools.items():
        lines.append(f"**{server_name}** ({len(tools)} tools):")
        for t in tools[:5]:
            lines.append(f"  • `{t.name}` — {(t.description or '')[:60]}")
        if len(tools) > 5:
            lines.append(f"  ... and {len(tools) - 5} more")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth_check(update):
        await update.message.reply_text("🚫 Not authorized.")
        return
    clear_history(str(update.effective_user.id))
    await update.message.reply_text("✅ Conversation history cleared.")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth_check(update):
        await update.message.reply_text("🚫 Not authorized.")
        return

    await update.message.reply_text(
        "🐉 *Dragonclawd Help*\n\n"
        "*Commands:*\n"
        "/start — Welcome message\n"
        "/status — Quick service status\n"
        "/mcp — Show MCP servers and tools\n"
        "/clear — Reset conversation history\n"
        "/help — This message\n\n"
        "*Image Generation:*\n"
        "• \"Generate an image of a dragon at sunset\"\n"
        "• \"Make a 16:9 image of... using Z-Image\"\n"
        "• \"Create a photo-realistic portrait with negative prompt 'cartoon'\"\n\n"
        "*Services:*\n"
        "• \"What services are running?\"\n"
        "• \"Start DragonFlux Klein\"\n"
        "• \"Stop the wan2gp service\"\n\n"
        "*System:*\n"
        "• \"How much VRAM is free?\"\n"
        "• \"What's the disk usage?\"\n"
        "• \"List my recent generated images\"\n\n"
        "*Knowledge Base (via MCP):*\n"
        "• \"Search my knowledge base for...\"\n"
        "• \"Read the file /srv/containers/edq/docs/venvs.md\"",
        parse_mode=ParseMode.MARKDOWN
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if not auth_check(update):
        log.warning(f"Unauthorized: id={update.effective_user.id} username={update.effective_user.username}")
        await update.message.reply_text("🚫 Not authorized.")
        return

    text = update.message.text or ""
    if not text.strip():
        return

    log.info(f"Message from {user_id}: {text[:100]}")

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )

    try:
        reply_text, attachments = await run_agent_loop(text, user_id)
    except Exception as e:
        log.error(f"Agent error: {e}", exc_info=True)
        reply_text = f"❌ Error: {e}"
        attachments = []

    # Send attachments (images, audio) before the text reply
    IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
    AUDIO_EXTS = {".wav", ".mp3", ".ogg", ".flac", ".m4a"}

    for attachment in attachments:
        try:
            ext = attachment.suffix.lower()
            with open(attachment, "rb") as f:
                if ext in IMAGE_EXTS:
                    await update.message.reply_photo(f)
                elif ext in AUDIO_EXTS:
                    await update.message.reply_audio(f)
                else:
                    await update.message.reply_document(f)
        except Exception as e:
            log.warning(f"Could not send attachment {attachment}: {e}")

    # Send text reply (Telegram limit: 4096 chars)
    if len(reply_text) > 4000:
        reply_text = reply_text[:3990] + "\n...(truncated)"

    try:
        await update.message.reply_text(reply_text, parse_mode=ParseMode.MARKDOWN)
    except Exception:
        # Fallback: send without markdown if it fails to parse
        await update.message.reply_text(reply_text)


# ── Main ──────────────────────────────────────────────────────────────────────

async def post_init(application: Application) -> None:
    """Called after the bot is initialized — start MCP servers here."""
    log.info("Starting MCP servers...")
    await mcp_manager.start()
    if mcp_manager.sessions:
        tool_count = sum(len(t) for t in mcp_manager.server_tools.values())
        log.info(f"MCP ready: {list(mcp_manager.sessions.keys())} ({tool_count} tools total)")
    else:
        log.info("No MCP servers connected (will still work without them)")

    await application.bot.set_my_commands([
        BotCommand("start", "Welcome message"),
        BotCommand("status", "Quick service status"),
        BotCommand("mcp", "MCP servers and tools"),
        BotCommand("clear", "Reset conversation history"),
        BotCommand("help", "Help and examples"),
    ])


async def post_shutdown(application: Application) -> None:
    """Called on shutdown — clean up MCP servers."""
    log.info("Shutting down MCP servers...")
    await mcp_manager.stop()


def main():
    if not BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not set in .env")
        print("   Get one from @BotFather in Telegram, then add to /srv/containers/edq/.env")
        return

    if not ALLOWED_USERS:
        print("⚠️  TELEGRAM_ALLOWED_USERS not set — bot will reject all messages!")
        print("   Get your ID from @userinfobot, then add to /srv/containers/edq/.env")

    if not ANTHROPIC_API_KEY:
        print("❌ ANTHROPIC_API_KEY not set in .env")
        return

    print("🐉 Dragonclawd starting...")
    print(f"   Allowed users: {ALLOWED_USERS if ALLOWED_USERS else 'NONE (set TELEGRAM_ALLOWED_USERS)'}")
    print(f"   Dragonsuite API: {DRAGONSUITE_API}")
    print(f"   Model: {anthropic_model()}")
    print(f"   MCP servers: {list(MCPManager.SERVER_CONFIGS.keys())}")
    print()

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("mcp", cmd_mcp))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🐉 Dragonclawd online — polling for messages...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
