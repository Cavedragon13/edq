#!/usr/bin/env python3
"""Bound the overnight agent's lifetime, make GPU room, and always put things back.

Policy (Ed, 2026-10-23): in the midnight-04:00 window, anything not actively working
may be stopped to get updates and tests done, as long as it comes back afterwards.

  1. Watch the GPU for IDLE_SAMPLE_S. If it is busy, someone is working: evict nothing
     (the agent can still do non-GPU work; GPU tests defer).
  2. If idle: stop every running GPU service (Krea2 included) and unload Ollama models,
     remembering exactly what was stopped.
  3. Run the agent with hard time limits.
  4. On any exit: stop the agent's own test services, then restart everything evicted
     in step 2 and confirm each one is running again.
"""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.request

from overnight_services import api, cleanup, holds_gpu, load, save

RUN_LIMIT_S = 90 * 60
TEST_LIMIT_S = 20 * 60
IDLE_SAMPLE_S = 60          # how long to watch GPU utilisation before deciding
BUSY_UTIL_PCT = 10          # average utilisation at or above this means "actively working"
RESTORE_WAIT_S = 180        # per service, for it to report running again
OLLAMA = "http://127.0.0.1:11434"


def gpu_used_mib():
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True, timeout=10, check=True)
    return int(out.stdout.strip().splitlines()[0])


def gpu_busy():
    samples = []
    for _ in range(IDLE_SAMPLE_S // 2):
        out = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu",
                              "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10, check=True)
        samples.append(int(out.stdout.strip().splitlines()[0]))
        time.sleep(2)
    average = sum(samples) / len(samples)
    return average >= BUSY_UTIL_PCT, average


def ollama_unload():
    """Free VRAM held by idle Ollama models. They reload on the next request by themselves."""
    unloaded = []
    try:
        with urllib.request.urlopen(OLLAMA + "/api/ps", timeout=10) as response:
            models = [m["name"] for m in json.load(response).get("models", [])]
        for name in models:
            body = json.dumps({"model": name, "keep_alive": 0}).encode()
            request = urllib.request.Request(OLLAMA + "/api/generate", data=body, method="POST",
                                             headers={"Content-Type": "application/json"})
            urllib.request.urlopen(request, timeout=30).read()
            unloaded.append(name)
    except Exception as exc:
        print(f"Ollama unload skipped: {exc}", flush=True)
    return unloaded


def running_ids():
    return {s["id"] for s in api("/api/status")["services"] if s["running"]}


def evict(services):
    """Stop running GPU services. Returns (stopped ids, problems)."""
    stopped, problems = [], []
    for service in services:
        if not (service["running"] and holds_gpu(service)):
            continue
        sid = service["id"]
        try:
            api("/api/stop/" + sid, post=True)
        except Exception as exc:
            problems.append(f"{sid}: stop failed: {exc}")
            continue
        for _ in range(30):
            if sid not in running_ids():
                break
            time.sleep(2)
        else:
            problems.append(f"{sid}: still running after stop")
            continue
        stopped.append(sid)
    return stopped, problems


def restore(ids):
    """Start each evicted service again and wait until it reports running. Returns failures."""
    failures = []
    for sid in ids:
        try:
            reply = api("/api/start/" + sid, post=True)
            if reply.get("status") == "vram_warning":
                # Only our own evictions are being undone; nothing of Ed's is in the way.
                reply = api(f"/api/start/{sid}?force=true", post=True)
            if reply.get("status") not in ("started", "already_running"):
                failures.append(f"{sid}: {reply}")
                continue
        except Exception as exc:
            failures.append(f"{sid}: start failed: {exc}")
            continue
        deadline = time.monotonic() + RESTORE_WAIT_S
        while sid not in running_ids():
            if time.monotonic() >= deadline:
                failures.append(f"{sid}: not running {RESTORE_WAIT_S}s after restart")
                break
            time.sleep(3)
    return failures


def main():
    journal = Path(os.environ["OVERNIGHT_SERVICE_JOURNAL"])
    report = Path(os.environ["OVERNIGHT_REPORT"])
    dry_run = os.environ.get("DRY_RUN") == "1"
    services = api("/api/status")["services"]
    preexisting = [s["id"] for s in services if s["running"]]
    evicted, unloaded, note = [], [], ""

    if not dry_run:
        busy, average = gpu_busy()
        if busy:
            note += (f"\nSupervisor: GPU busy at entry (avg {average:.0f}% over {IDLE_SAMPLE_S}s);"
                     " nothing was stopped, GPU tests deferred.")
        else:
            evicted, problems = evict(services)
            unloaded = ollama_unload()
            note += (f"\nSupervisor: GPU idle at entry (avg {average:.0f}%). Stopped for room:"
                     f" {', '.join(evicted) or 'nothing'}; unloaded Ollama: {', '.join(unloaded) or 'none'}.")
            if problems:
                note += f" Could not stop: {'; '.join(problems)}."

    baseline = gpu_used_mib()
    state = {"dry_run": dry_run, "preexisting": preexisting, "evicted": evicted,
             "owned": {}, "baseline_mib": baseline}
    save(journal, state)
    child = None
    rc = 1

    def interrupted(signum, frame):
        raise InterruptedError(f"received signal {signum}")

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        child = subprocess.Popen(sys.argv[1:], start_new_session=True)
        deadline = time.monotonic() + RUN_LIMIT_S
        while child.poll() is None:
            state = load(journal, state)  # rebuilt from memory if the file goes missing
            running = running_ids()
            expired = [sid for sid, started in state["owned"].items()
                       if time.time() - started > TEST_LIMIT_S and sid in running]
            if time.monotonic() >= deadline or expired:
                raise TimeoutError(f"Run or service time limit reached: {expired}")
            time.sleep(5)
        rc = child.returncode
    except Exception as exc:
        note += f"\n{exc}"
        print(exc, flush=True)
    finally:
        # No second TERM can interrupt cleanup.
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        if child is not None:
            try:
                os.killpg(child.pid, signal.SIGTERM)
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
            except ProcessLookupError:
                pass
        try:
            if not dry_run:
                cleanup(journal, state)
            final_mib = gpu_used_mib()
            note += ("\nSupervisor: agent test services stopped."
                     f" GPU memory: after eviction {baseline} MiB, before restore {final_mib} MiB.")
            if final_mib > baseline + 256:
                rc = 1
                note += " GPU memory did not return to baseline; inspect."
        except Exception as exc:
            rc = 1
            note += f"\nCLEANUP FAILED: {exc}"
        if evicted:
            failures = restore(evicted)
            if failures:
                rc = 1
                note += f"\nNEEDS ED — could not bring back: {'; '.join(failures)}"
            else:
                note += f"\nSupervisor: restored and verified running: {', '.join(evicted)}."
        if not report.exists():
            report.write_text("# Overnight\n\nAgent did not complete its morning report.\n")
        with report.open("a") as stream:
            stream.write(f"\nSupervisor exit: {rc}.{note}\n")
    return rc


if __name__ == "__main__":
    sys.exit(main())
