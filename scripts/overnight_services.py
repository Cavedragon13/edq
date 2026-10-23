#!/usr/bin/env python3
"""Durable ownership journal for the unattended agent's test services.

Policy (Ed, 2026-10-23): between midnight and 04:00 anything that is not actively
working may be stopped, as long as it is brought back afterwards. The supervisor
does that eviction and restore; this module only tracks the agent's own tests.
"""
import json
import os
from pathlib import Path
import sys
import subprocess
import time
import urllib.request

BASE = "http://127.0.0.1:8100"
EXCLUDED_TESTS = ("auk", "minimax-music3")  # deferred to a supervised session with Ed


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


def load(path, fallback=None):
    """Read the journal; if it has gone missing, rebuild it from the fallback."""
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        if fallback is None:
            raise
        save(path, fallback)
        return json.loads(json.dumps(fallback))


def protected(service):
    """Krea2's launcher, files and LoRAs are never test subjects (it may be evicted)."""
    return service["id"].startswith("krea2")


def holds_gpu(service):
    return bool(service.get("vram_gb") or service.get("live_vram_gb") or protected(service))


def start(path, sid):
    state = load(path)
    services = api("/api/status")["services"]
    service = next(s for s in services if s["id"] == sid)
    if protected(service) or sid in EXCLUDED_TESTS:
        raise RuntimeError("Service excluded from unattended testing")
    # Evicted services are stopped now and restored by the supervisor, so they may be tested.
    still_up = set(state["preexisting"]) - set(state.get("evicted", []))
    if state["dry_run"] or sid in still_up or service["running"]:
        raise RuntimeError("Dry run or service already running; ownership refused")
    if any(s["running"] and holds_gpu(s) for s in services):
        raise RuntimeError("A GPU service is running (GPU was busy at entry, so nothing "
                           "was evicted); defer this test")
    gpu = subprocess.run(["nvidia-smi", "--query-compute-apps=used_memory",
                          "--format=csv,noheader,nounits"], check=True,
                         capture_output=True, text=True, timeout=10)
    if any(int(line.strip()) > 1500 for line in gpu.stdout.splitlines() if line.strip()):
        raise RuntimeError("GPU is in use; defer this test")
    state["owned"][sid] = time.time()
    save(path, state)  # durable BEFORE requesting a detached dashboard launch
    print(json.dumps(api("/api/start/" + sid, post=True)))


def cleanup(path, fallback=None):
    """Stop every test service the agent started. Never stops pre-existing services."""
    state = load(path, fallback)
    keep = set(state.get("preexisting", [])) - set(state.get("evicted", []))
    failures = []
    for sid in state["owned"]:
        if sid in keep or sid.startswith("krea2"):
            continue
        try:
            print(json.dumps(api("/api/stop/" + sid, post=True)))
        except Exception as exc:
            failures.append(f"{sid}: {exc}")
    # Check twice: a detached launcher can still be starting when stop is sent.
    remaining = []
    for attempt in range(10):
        services = api("/api/status")["services"]
        remaining = [s["id"] for s in services if s["running"]
                     and s["id"] in state["owned"]
                     and s["id"] not in keep and not protected(s)]
        for sid in remaining:
            api("/api/stop/" + sid, post=True)
        if attempt >= 1 and not remaining:
            break
        time.sleep(2)
    if remaining or failures:
        raise RuntimeError(f"Cleanup needs attention: {remaining}; {failures}")


if __name__ == "__main__":
    action, filename, *rest = sys.argv[1:]
    journal = Path(filename)
    if action == "start":
        start(journal, rest[0])
    elif action == "cleanup":
        cleanup(journal)
    else:
        raise SystemExit("Expected start or cleanup")
