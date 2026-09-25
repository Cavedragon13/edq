#!/usr/bin/env python3
"""
Dragonsuite Service Health Check
Weekly rotation: structural integrity checks — does NOT launch GPU services.

Besides the basic checks (start script, port conflicts, stop command, output
dir, always-on reachability) every service is held to the Dragonsuite standard.
These rules are the written-down version of what "set up correctly" means, so
drift is caught the night it happens instead of by an occasional manual sweep:

  [update]   project is updatable: a real git repo (not an orphaned worktree),
             third-party code tracks an upstream branch, no uncommitted edits
  [stuck]    weekly_update.sh has failed on it for 2+ weeks
  [vram]     GPU launcher uses vram_guard (vram_preflight + register_tool),
             not the evict-everything gpu_preflight
  [download] GPU service has a model download script (no first-run downloads)
  [output]   output_dir is actually referenced by the code that writes to it
  [venv]     the venv the launcher names exists

Usage:
  python3 scripts/health_check.py --categories audio music
  python3 scripts/health_check.py --categories image
  python3 scripts/health_check.py --all
"""

import argparse
import datetime as dt
import json
import os
import re
import socket
import subprocess
import sys
from collections import Counter
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
    25600: ("minidragon", "Komga"),
    8123: ("minidragon", "Home Assistant"),
    8222: ("minidragon", "Vaultwarden"),
}

ALWAYS_ON_HOSTS = {
    "udragon": "127.0.0.1",
    "minidragon": "192.168.7.114",
}

VISION_GENERATIVE = {
    "sam2", "rembg", "facefusion", "matanyone2", "liveportrait",
    "qwen-image-layered", "triposplat", "asset3d",
}

# ---- Dragonsuite-standard conformance -------------------------------------

OWN_REMOTE_MARKERS = ("Cavedragon13",)      # GitHub owner of Ed's own repos
STUCK_STATE = LOG_DIR / "weekly_update_stuck.json"
# Third-party checkouts that are intentionally pinned, and what keeps them current.
PINNED_OK = {
    "comfyui": "comfy-cli release tags, rolled forward by weekly_update.sh",
}
# Services whose project folder is a platform that updates its own contents.
MANAGED_ELSEWHERE = {
    "pinokio": "Pinokio updates its own apps (Update button / script.pull)",
}
REGISTERED_PROJECTS: set[str] = set()   # filled in run(): every service's project_path
SCRIPTS_DIR = BASE / "scripts"


def _git(path: Path, *args: str) -> str:
    try:
        r = subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True, timeout=20)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def launcher_scripts(svc: dict) -> list[Path]:
    """Local scripts named in launch_command that exist on disk."""
    found = []
    for token in (svc.get("launch_command") or "").split():
        if token.endswith(".sh") or (token.endswith(".py") and "scripts/" in token):
            p = Path(token) if token.startswith("/") else BASE / token
            if p.exists():
                found.append(p)
    return found


def _script_text(paths: list[Path]) -> str:
    """Launcher text plus any scripts/*.py server it starts (one level deep)."""
    text = ""
    for p in paths:
        try:
            t = p.read_text(errors="replace")
        except OSError:
            continue
        text += t
        for py in re.findall(r"scripts/([\w.-]+\.py)", t):
            try:
                text += (SCRIPTS_DIR / py).read_text(errors="replace")
            except OSError:
                pass
    return text


def runs_remotely(svc: dict) -> bool:
    """Launched over SSH on another machine (e.g. MLX services on the Macs):
    VRAM, download and output rules are the remote host's business."""
    return bool(re.search(r"^\s*ssh\s", _script_text(launcher_scripts(svc)), re.M))


def check_update_path(svc: dict) -> tuple[list[str], list[str]]:
    """[update] Can weekly_update.sh actually keep this project current?"""
    issues, warnings = [], []
    pp = svc.get("project_path")
    sid = svc.get("id", "")
    if not pp:
        # A launcher that runs code from projects/<x> without declaring it is
        # invisible to the updater.
        text = _script_text(launcher_scripts(svc))
        for proj in sorted(set(re.findall(r"projects/([A-Za-z0-9_.-]+)", text))):
            d = BASE / "projects" / proj
            if str(d) in REGISTERED_PROJECTS:
                continue   # another service owns (and updates) this project, e.g. ComfyUI
            if (d / ".git").exists():
                remote = _git(d, "remote", "get-url", "origin")
                if remote and not any(m in remote for m in OWN_REMOTE_MARKERS):
                    warnings.append(f"[update] runs third-party code from projects/{proj} but project_path is unset — weekly updater can't see it")
        return issues, warnings

    if sid in MANAGED_ELSEWHERE:
        return issues, warnings
    path = Path(pp)
    if not path.exists():
        return [f"[update] project_path does not exist: {pp}"], warnings
    dotgit = path / ".git"
    if dotgit.is_file():
        target = dotgit.read_text(errors="replace").replace("gitdir:", "").strip()
        if not Path(target).exists():
            return [f"[update] orphaned git worktree — .git points at missing {target}; invisible to all git updates"], warnings
    if not dotgit.exists():
        top = _git(path, "rev-parse", "--show-toplevel")
        if top and Path(top) == BASE:
            ignored = subprocess.run(["git", "-C", str(BASE), "check-ignore", "-q", str(path)]).returncode == 0
            if ignored:
                warnings.append("[update] own code inside edq but git-ignored — not version-controlled or backed up by the nightly commit")
            return issues, warnings
        return [f"[update] no git repo at {pp} — updater can't see it (reinstall as a git clone)"], warnings

    remote = _git(path, "remote", "get-url", "origin")
    own = (not remote) or any(m in remote for m in OWN_REMOTE_MARKERS)
    upstream = _git(path, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if not own and not upstream:
        if sid in PINNED_OK:
            pass
        else:
            issues.append(f"[update] third-party checkout has no upstream tracking branch (detached/pinned) — never auto-updated ({remote})")
    dirty = _git(path, "status", "--porcelain", "--untracked-files=no")
    if dirty:
        n = len(dirty.splitlines())
        if own:
            warnings.append(f"[update] {n} uncommitted edit(s) in your own repo — commit/push so the work is saved")
        else:
            warnings.append(f"[update] {n} uncommitted local edit(s) — commit them as a patch or the updater will conflict on them")
    return issues, warnings


def check_stuck(svc: dict, stuck: dict) -> list[str]:
    """[stuck] Failing in weekly_update.sh for 2+ weeks."""
    first = stuck.get(svc.get("name", ""))
    if not first:
        return []
    weeks = (dt.date.today() - dt.date.fromisoformat(first)).days // 7
    return [f"[stuck] weekly update failing since {first} ({weeks} wk) — see logs/weekly_update_attention.md"] if weeks >= 2 else []


def check_launcher_standard(svc: dict) -> tuple[list[str], list[str]]:
    """[vram] [download] [venv] Launcher follows the dragonsuite-add standard."""
    issues, warnings = [], []
    scripts = [p for p in launcher_scripts(svc) if p.name.startswith("start_")]
    if not scripts:
        return issues, warnings
    text = _script_text(scripts)
    gpu = (svc.get("vram_gb") or 0) > 0

    m = re.search(r'^VENV="([^"]+)"', text, re.M)
    if m:
        venv = re.sub(r"^\$\{?\w+\}?/", "", m.group(1))   # "$ROOT_DIR/venv_x" -> "venv_x"
        if not (Path(venv) if venv.startswith("/") else BASE / venv).exists():
            issues.append(f"[venv] launcher names {m.group(1)} but it does not exist")

    if gpu:
        if "gpu_preflight" in text:
            warnings.append("[vram] uses gpu_preflight (evicts every GPU process) — switch to vram_guard: REQ_VRAM_MIB + vram_preflight + register_tool")
        elif "vram_preflight" not in text:
            warnings.append("[vram] GPU service with no VRAM gate — add vram_guard (REQ_VRAM_MIB + vram_preflight + register_tool)")
        elif "register_tool" not in text:
            warnings.append("[vram] vram_preflight without register_tool — CLEAR=1 can't stop this service")

        stem = scripts[0].stem.replace("start_", "").replace("_native", "")
        sid = svc.get("id", "").replace("-", "_")
        tokens = {stem, sid, stem.split("_")[0], sid.split("_")[0]} - {""}
        has_dl = "download_" in text or any(
            any(t in p.name for t in tokens) for p in SCRIPTS_DIR.glob("*download*"))
        if not has_dl:
            warnings.append("[download] no model download script — first launch would download models (SOP: scripts/download_<service>_models.sh)")
    return issues, warnings


def check_output_wiring(svc: dict) -> list[str]:
    """[output] output_dir is referenced by the code that writes there."""
    od = svc.get("output_dir")
    if not od or not needs_output_dir(svc) or not Path(od).exists():
        return []
    if Path(od).is_symlink():
        return []   # Pattern A: ai_generated/<svc> -> the tool's own output folder
    scripts = launcher_scripts(svc)
    if not scripts:
        return []
    text = _script_text(scripts)
    base = Path(od).name
    # matches ai_generated/<base>, "ai_generated" / "<base>", ai_generated", "<base>" ...
    pattern = r"ai_generated\W{0,6}" + re.escape(base) + r"\b"
    if od in text or re.search(pattern, text):
        return []
    # the server may live inside a project folder the launcher points at
    projects = {BASE / "projects" / d for d in re.findall(r"projects/([A-Za-z0-9_.-]+)", text)}
    if svc.get("project_path"):
        projects.add(Path(svc["project_path"]))
    for d in projects:
        if d.is_dir():
            try:
                r = subprocess.run(["grep", "-rlEq", "--include=*.py", "--exclude-dir=.venv", "--exclude-dir=venv",
                                    "--exclude-dir=node_modules", "--exclude-dir=site-packages", pattern, str(d)],
                                   capture_output=True, timeout=60)
            except subprocess.TimeoutExpired:
                continue
            if r.returncode == 0:
                return []
    return [f"[output] {od} exists but nothing in the launcher/server references it — outputs may be landing elsewhere"]


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


def check_service(svc: dict, port_registry: dict, stuck: dict | None = None) -> tuple[str, list[str]]:
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

    # Dragonsuite-standard conformance
    i, w = check_update_path(svc)
    issues += i
    warnings += w
    issues += check_stuck(svc, stuck or {})
    if not runs_remotely(svc):
        i, w = check_launcher_standard(svc)
        issues += i
        warnings += w
        warnings += check_output_wiring(svc)

    if issues:
        return "FAIL", issues + warnings
    if warnings:
        return "WARN", warnings
    return "PASS", []


RULE_TITLES = {
    "basic": "Basic checks (script, port, output dir, always-on reachability)",
    "stuck": "Weekly update stuck 2+ weeks",
    "update": "Not keepable up to date (git / upstream / uncommitted edits)",
    "vram": "Launcher not on the VRAM gate (vram_guard)",
    "download": "No model download script",
    "output": "Output folder not wired to the code that writes",
    "venv": "Launcher's venv missing",
}
# Lives in the Obsidian vault (Syncthing → the Macs) so it's read, not buried in logs/.
CONFORMANCE_MD = Path.home() / "knowledge-base" / "Dragonsuite" / "Conformance.md"
CONFORMANCE_HISTORY = LOG_DIR / "conformance_history.json"   # {date: services off-standard}


def _trend(count: int) -> str:
    """Record today's count; describe the change vs. yesterday and ~a week ago."""
    today = dt.date.today()
    try:
        hist = json.loads(CONFORMANCE_HISTORY.read_text())
    except (OSError, ValueError):
        hist = {}
    hist[today.isoformat()] = count
    hist = {d: c for d, c in hist.items() if (today - dt.date.fromisoformat(d)).days <= 90}
    CONFORMANCE_HISTORY.write_text(json.dumps(hist, indent=1, sort_keys=True))
    past = sorted(d for d in hist if d < today.isoformat())
    parts = []
    if past:
        parts.append(f"{hist[past[-1]]} on {past[-1]}")
        week = [d for d in past if (today - dt.date.fromisoformat(d)).days >= 7]
        if week:
            parts.append(f"{hist[week[-1]]} a week ago ({week[-1]})")
    return f"**{count} services off-standard**" + (f" — was {', '.join(parts)}" if parts else "")


def write_conformance_snapshot(ts: str, by_rule: dict, fails_detail: list) -> None:
    """Overwrite Dragonsuite/Conformance.md: the current list of off-standard services."""
    off = {n for rule, items in by_rule.items() if rule != "basic" for n, _ in items}
    out = [f"# Dragonsuite conformance — {ts}", "",
           _trend(len(off)), "",
           "Auto-generated nightly by `scripts/health_check.py --all` on udragon (rules in its docstring).",
           "This is the live to-do list: fix a service and it drops off the next night.", ""]
    if fails_detail:
        out += ["## FAIL", ""] + [f"- **{n}** — " + "; ".join(d) for n, d in fails_detail] + [""]
    for rule in ("stuck", "update", "vram", "download", "output", "venv"):
        items = by_rule.get(rule)
        if items:
            out += [f"## {RULE_TITLES[rule]} ({len(items)})", ""]
            out += [f"- **{n}** — {re.sub(r'^\[\w+\]\s*', '', d)}" for n, d in items] + [""]
    if not off and not fails_detail:
        out.append("Everything conforms. 🎉")
    CONFORMANCE_MD.parent.mkdir(parents=True, exist_ok=True)
    CONFORMANCE_MD.write_text("\n".join(out) + "\n")


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

    try:
        stuck = json.loads(STUCK_STATE.read_text())
    except (OSError, ValueError):
        stuck = {}
    rule_tally: Counter = Counter()
    by_rule: dict[str, list[tuple[str, str]]] = {}
    fails_detail: list[tuple[str, list[str]]] = []
    REGISTERED_PROJECTS.update(s["project_path"].rstrip("/") for s in services if s.get("project_path"))

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
        status, details = check_service(svc, port_registry, stuck)
        checked += 1
        for d in details:
            m = re.match(r"\[(\w+)\]", d)
            rule = m.group(1) if m else "basic"
            rule_tally[rule] += 1
            by_rule.setdefault(rule, []).append((name, d))
        if status == "FAIL":
            fails_detail.append((name, details))

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
    if rule_tally:
        lines.append("Findings by rule: " + ", ".join(f"{k} {v}" for k, v in sorted(rule_tally.items())))
    lines.append("")

    report = "\n".join(lines)
    print(report)

    if check_all:
        write_conformance_snapshot(ts, by_rule, fails_detail)

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
