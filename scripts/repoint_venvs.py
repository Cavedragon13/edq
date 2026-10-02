#!/usr/bin/env python3
"""Repoint venv_* interpreters from the OS Python (/usr/bin) to uv-managed standalone Pythons.

Why: venvs whose pyvenv.cfg says `home = /usr/bin` break when an OS release upgrade swaps or
removes the system Python (Ubuntu 24.04 -> 26.04, deadsnakes 3.10). uv's standalone builds live
in ~/.local/share/uv/python and survive OS upgrades.

Usage:
    python3 scripts/repoint_venvs.py --dry-run [venv_name ...]
    python3 scripts/repoint_venvs.py --apply   [venv_name ...]   # no names = all venvs
    python3 scripts/repoint_venvs.py --rollback [venv_name ...]

A rollback manifest is written to logs/venv_repoint_manifest.json before any change.
Only the interpreter links and `home =` in pyvenv.cfg change; site-packages is untouched.
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys

ROOT = "/srv/containers/edq"
MANIFEST = f"{ROOT}/logs/venv_repoint_manifest.json"


def uv_python_dir(minor):
    out = subprocess.run(["uv", "python", "find", minor], capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit(f"uv has no Python {minor}: run `uv python install {minor}`")
    exe = os.path.realpath(out.stdout.strip())
    return os.path.dirname(exe)  # .../bin


def load_manifest():
    if os.path.exists(MANIFEST):
        return json.load(open(MANIFEST))
    return {}


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    g.add_argument("--rollback", action="store_true")
    ap.add_argument("names", nargs="*")
    a = ap.parse_args()

    venvs = sorted(glob.glob(f"{ROOT}/venv_*"))
    if a.names:
        venvs = [v for v in venvs if os.path.basename(v) in a.names]
    manifest = load_manifest()

    for v in venvs:
        name = os.path.basename(v)
        cfg_path = f"{v}/pyvenv.cfg"
        if not os.path.exists(cfg_path):
            print(f"SKIP {name}: no pyvenv.cfg")
            continue
        cfg = open(cfg_path).read()
        home = re.search(r"^home\s*=\s*(.+)$", cfg, re.M).group(1).strip()
        ver = re.search(r"^version(?:_info)?\s*=\s*(\d+\.\d+)", cfg, re.M).group(1)
        minor = ver
        bindir = f"{v}/bin"
        links = {f: os.readlink(f"{bindir}/{f}") for f in os.listdir(bindir)
                 if f.startswith("python") and os.path.islink(f"{bindir}/{f}")}

        if a.rollback:
            m = manifest.get(name)
            if not m:
                print(f"SKIP {name}: no manifest entry")
                continue
            open(cfg_path, "w").write(m["cfg"])
            for f, tgt in m["links"].items():
                p = f"{bindir}/{f}"
                if os.path.islink(p):
                    os.remove(p)
                os.symlink(tgt, p)
            print(f"ROLLED BACK {name}")
            continue

        if home != "/usr/bin" and not home.startswith("/usr/"):
            print(f"SKIP {name}: home={home} (already managed)")
            continue

        new_bin = uv_python_dir(minor)
        print(f"{'WOULD ' if a.dry_run else ''}REPOINT {name}: {home} (py{ver}) -> {new_bin}")
        if a.dry_run:
            continue

        manifest[name] = {"cfg": cfg, "links": links}
        os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
        json.dump(manifest, open(MANIFEST, "w"), indent=1)

        open(cfg_path, "w").write(re.sub(r"^home\s*=.*$", f"home = {new_bin}", cfg, flags=re.M))
        for f, tgt in links.items():
            if os.path.isabs(tgt):  # only absolute links point at the OS Python
                p = f"{bindir}/{f}"
                os.remove(p)
                os.symlink(f"{new_bin}/python{minor}", p)


if __name__ == "__main__":
    main()
