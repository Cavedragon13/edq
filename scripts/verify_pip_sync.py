#!/usr/bin/env python3
"""Verify that every exact-pinned (==) requirement is actually installed at
that version. `pip install -r requirements.txt --upgrade` can exit 0 while
still leaving an exact pin at the wrong version if the dependency graph
needs more than one resolver pass to converge (observed 2026-08-19 with
Wan2GP's mmgp==3.7.11 pin landing at 3.7.12 after a single sync).

Usage: verify_pip_sync.py <requirements.txt> <venv_python_bin>
Exit 0 and no output if all exact pins match.
Exit 1 and one "name: wants X, installed is Y" line per mismatch otherwise.
"""
import re
import subprocess
import sys


def normalize(name):
    # PEP 503: pip/PyPI treat runs of -, _, . as equivalent and case-insensitive
    # (e.g. "vector_quantize_pytorch" == "vector-quantize-pytorch"). A naive
    # string compare treats those as different packages and reports a false
    # "missing" even when pip itself considers the requirement satisfied.
    return re.sub(r"[-_.]+", "-", name).lower()


req_file, python_bin = sys.argv[1], sys.argv[2]

pins = {}
with open(req_file) as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9_.\-]+)==([A-Za-z0-9_.\-]+)\s*$", line)
        if m:
            pins[normalize(m.group(1))] = m.group(2)

if not pins:
    sys.exit(0)

result = subprocess.run(
    [python_bin, "-m", "pip", "list", "--format=freeze"],
    capture_output=True, text=True,
)
installed = {}
for line in result.stdout.splitlines():
    if "==" in line:
        name, ver = line.split("==", 1)
        installed[normalize(name)] = ver

mismatches = [
    f"{name}: requirements.txt wants {want}, installed is {installed.get(name, 'MISSING')}"
    for name, want in pins.items()
    if installed.get(name) != want
]

if mismatches:
    print("\n".join(mismatches))
    sys.exit(1)
sys.exit(0)
