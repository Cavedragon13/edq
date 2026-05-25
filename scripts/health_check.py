#!/usr/bin/env python3
"""
Dragonsuite Service Health Check
Weekly rotation: structural integrity checks — does NOT launch GPU services.

Usage:
  python3 scripts/health_check.py --categories audio music
  python3 scripts/health_check.py --categories image
  python3 scripts/health_check.py --all
"""

import argparse
import json
import os
import socket
import sys
from datetime import datetime
from pathlib import Path

BASE = Path("/srv/containers/edq")
CONFIG = BASE / "config" / "dragonsuite.json"
LOG_DIR = BASE / "logs"
LOG_FILE = LOG_DIR / "health_check.log"

GENERATIVE_CATEGORIES = {"image", "video", "audio", "music"}

ALWAYS_ON = {
    11434: ("udragon", "Ollama API"),
    8096: ("minidragon", "Jellyfin"),
    2283: ("minidragon", "Immich"),
    4533: ("minidragon", "Navidrome"),
    9000: ("minidragon", "Portainer"),
}

ALWAYS_ON_HOSTS = {
    "udragon": "127.0.0.1",
    "minidragon": "192.168.7.114",
}

VISION_GENERATIVE = {
    "sam2", "rembg", "facefusion", "matanyone2", "liveportrait",
    "qwen-image-layered", "hunyuan3d",
}


def check_port_conflict(port: int, name: str, port_registry: dict) -> str | None:
    if port in port_registry:
        other = port_registry[port]
        if other != name:
            return f"PORT CONFLICT {port}: also claimed by '{other}'"
    return None


def ping_port(host: str, port: int, timeout: float = 2.0) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        try:
            s.connect((host, port))
            return True
        except Exception:
            return False


def needs_output_dir(svc: dict) -> bool:
    cat = svc.get("category", "")
    if cat in GENERATIVE_CATEGORIES:
        if svc.get("id") == "topaz-labs":
            return False
        return True
    if cat == "vision" and svc.get("id") in VISION_GENERATIVE:
        return True
    return False


def check_service(svc: dict, port_registry: dict) -> tuple[str, list[str]]:
    name = svc.get("name", svc.get("id", "?"))
    issues = []
    warnings = []

    launch_cmd = svc.get("launch_command", "")
    if launch_cmd:
        for token in launch_cmd.split():
            if token.endswith(".sh") or (token.endswith(".py") and "scripts/" in token):
                if token.startswith("/"):
                    script_path = Path(token)
                else:
                    script_path = BASE / token
                if not script_path.exists():
                    issues.append(f"start script missing: {script_path}")

    port = svc.get("port")
    if port:
        conflict = check_port_conflict(port, name, port_registry)
        if conflict:
            issues.append(conflict)

    has_launch = bool(svc.get("launch_command"))
    if not svc.get("stop_command") and port and has_launch:
        warnings.append("no stop_command (dashboard will kill by port)")

    if needs_output_dir(svc):
        od = svc.get("output_dir")
        if not od:
            issues.append(f"output_dir missing for generative service (category={svc.get('category')})")
        elif not Path(od).exists():
            issues.append(f"output_dir does not exist on disk: {od}")

    if port in ALWAYS_ON:
        machine, label = ALWAYS_ON[port]
        host = ALWAYS_ON_HOSTS.get(machine, "127.0.0.1")
        if not ping_port(host, port):
            issues.append(f"always-on service unreachable at {host}:{port}")

    if issues:
        return "FAIL", issues
    if warnings:
        return "WARN", warnings
    return "PASS", []


def run(categories: list[str] | None, check_all: bool) -> int:
    with open(CONFIG) as f:
        data = json.load(f)
    services = data["services"]

    port_registry: dict[int, str] = {}
    for svc in services:
        p = svc.get("port")
        if p:
            name = svc.get("name", svc.get("id", "?"))
            if p not in port_registry:
                port_registry[p] = name

    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    scope = "ALL" if check_all else " ".join(categories or [])
    header = f"\n{'='*60}\nHealth Check — {ts} — {scope}\n{'='*60}"

    lines = [header]
    fails = 0
    warns = 0
    checked = 0

    for svc in services:
        cat = svc.get("category", "")
        if not check_all and categories and cat not in categories:
            continue

        name = svc.get("name", svc.get("id", "?"))
        status, details = check_service(svc, port_registry)
        checked += 1

        if status == "FAIL":
            fails += 1
            lines.append(f"  FAIL  {name}")
            for d in details:
                lines.append(f"        ↳ {d}")
        elif status == "WARN":
            warns += 1
            lines.append(f"  WARN  {name}")
            for d in details:
                lines.append(f"        ↳ {d}")
        else:
            lines.append(f"  pass  {name}")

    summary = f"\nChecked: {checked} | FAIL: {fails} | WARN: {warns} | PASS: {checked - fails - warns}"
    lines.append(summary)
    lines.append("")

    report = "\n".join(lines)
    print(report)

    LOG_DIR.mkdir(exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(report)

    return 1 if fails > 0 else 0


def main():
    parser = argparse.ArgumentParser(description="Dragonsuite health check")
    parser.add_argument("--categories", nargs="+", metavar="CAT",
                        help="categories to check (e.g. audio music image)")
    parser.add_argument("--all", action="store_true", help="check all categories")
    args = parser.parse_args()

    if not args.all and not args.categories:
        parser.error("specify --all or --categories")

    sys.exit(run(args.categories, args.all))


if __name__ == "__main__":
    main()
