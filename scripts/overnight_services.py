#!/usr/bin/env python3
"""Durable ownership journal for the unattended agent's test services."""
import json
import os
from pathlib import Path
import sys
import subprocess
import time
import urllib.request

BASE = "http://127.0.0.1:8100"


def api(path, post=False):
    request = urllib.request.Request(BASE + path, method="POST" if post else "GET")
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.load(response)


def save(path, data):
    temporary = path.with_suffix(".tmp")
    with temporary.open("w") as stream:
        json.dump(data, stream)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def protected(service):
    return service["id"].startswith("krea2")


def start(path, sid):
    state = json.loads(path.read_text())
    services = api("/api/status")["services"]
    service = next(s for s in services if s["id"] == sid)
    if protected(service) or sid in ("auk", "minimax-music3"):
        raise RuntimeError("Service excluded from unattended testing")
    if state["dry_run"] or sid in state["preexisting"] or service["running"]:
        raise RuntimeError("Dry run or service already running; ownership refused")
    if any(s["running"] and (protected(s) or s.get("vram_gb")) for s in services):
        raise RuntimeError("A GPU service is running; defer this test without evicting it")
    gpu = subprocess.run(["nvidia-smi", "--query-compute-apps=used_memory",
                          "--format=csv,noheader,nounits"], check=True,
                         capture_output=True, text=True, timeout=10)
    if any(int(line.strip()) > 1500 for line in gpu.stdout.splitlines() if line.strip()):
        raise RuntimeError("GPU is in use; defer without evicting the current process")
    state["owned"][sid] = time.time()
    save(path, state)  # durable BEFORE requesting a detached dashboard launch
    print(json.dumps(api("/api/start/" + sid, post=True)))


def cleanup(path):
    state = json.loads(path.read_text())
    failures = []
    for sid in state["owned"]:
        if sid in state["preexisting"] or sid.startswith("krea2"):
            continue
        try:
            print(json.dumps(api("/api/stop/" + sid, post=True)))
        except Exception as exc:
            failures.append(f"{sid}: {exc}")
    # Check twice: a detached launcher can still be starting when stop is sent.
    for attempt in range(10):
        services = api("/api/status")["services"]
        remaining = [s["id"] for s in services if s["running"]
                     and s["id"] in state["owned"]
                     and s["id"] not in state["preexisting"] and not protected(s)]
        if remaining:
            for sid in remaining:
                api("/api/stop/" + sid, post=True)
        if attempt >= 1 and not remaining:
            break
        time.sleep(2)
    if remaining or failures:
        raise RuntimeError(f"Cleanup needs attention: {remaining}; {failures}")


if __name__ == "__main__":
    action, filename, *rest = sys.argv[1:]
    path = Path(filename)
    if action == "start":
        start(path, rest[0])
    elif action == "cleanup":
        cleanup(path)
    else:
        raise SystemExit("Expected start or cleanup")
