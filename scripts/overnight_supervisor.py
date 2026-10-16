#!/usr/bin/env python3
"""Bound agent lifetime; always clean up journaled test services on exit."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from overnight_services import api, cleanup, save


def main():
    journal = Path(os.environ["OVERNIGHT_SERVICE_JOURNAL"])
    report = Path(os.environ["OVERNIGHT_REPORT"])
    dry_run = os.environ.get("DRY_RUN") == "1"
    gpu = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True, timeout=10, check=True)
    baseline = int(gpu.stdout.strip().splitlines()[0])
    services = api("/api/status")["services"]
    save(journal, {"dry_run": dry_run, "preexisting": [s["id"] for s in services if s["running"]],
                   "owned": {}, "baseline_mib": baseline})
    child = None
    rc = 1
    note = ""

    def interrupted(signum, frame):
        raise InterruptedError(f"received signal {signum}")

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        child = subprocess.Popen(sys.argv[1:], start_new_session=True)
        deadline = time.monotonic() + 90 * 60
        while child.poll() is None:
            state = json.loads(journal.read_text())
            expired = [sid for sid, started in state["owned"].items()
                       if time.time() - started > 20 * 60
                       and any(s["id"] == sid and s["running"] for s in api("/api/status")["services"])]
            if time.monotonic() >= deadline or expired:
                raise TimeoutError(f"Run or service time limit reached: {expired}")
            time.sleep(5)
        rc = child.returncode
    except Exception as exc:
        note = str(exc)
        print(note, flush=True)
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
                cleanup(journal)
            reading = subprocess.run(["nvidia-smi", "--query-gpu=memory.used",
                                      "--format=csv,noheader,nounits"], check=True,
                                     capture_output=True, text=True, timeout=10)
            final_mib = int(reading.stdout.strip().splitlines()[0])
            note += ("\nSupervisor: recorded test services stopped; pre-existing services preserved."
                     f" GPU memory: entry {baseline} MiB, exit {final_mib} MiB.")
            if final_mib > baseline + 256:
                rc = 1
                note += " GPU memory did not return to entry baseline; inspect before retrying."
        except Exception as exc:
            rc = 1
            note += f"\nCLEANUP FAILED: {exc}"
        if not report.exists():
            report.write_text("# Overnight\n\nAgent did not complete its morning report.\n")
        with report.open("a") as stream:
            stream.write(f"\nSupervisor exit: {rc}. {note}\n")
    return rc


if __name__ == "__main__":
    sys.exit(main())
