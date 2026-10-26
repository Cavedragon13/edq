#!/usr/bin/env python3
"""End-to-end test for Qwen-Image 2.1 Studio through its Gradio API (the real UI path).

Runs against the live app on :8076 while sampling GPU memory with nvidia-smi (whole-card
used MiB, plus the server process's own MiB) so peak VRAM per test is measured, not guessed.
Writes a JSON report next to the outputs.

Usage: venv_qwen_image_21/bin/python scripts/test_qwen_image_21.py [--only t2i_preview,...]
"""
import argparse
import json
import subprocess
import threading
import time
from pathlib import Path

import numpy as np
from gradio_client import Client, handle_file
from PIL import Image

URL = "http://127.0.0.1:8076/"
REPORT = Path("/home/edq/ai_generated/test-artifacts/images/qwen-image-21/test_report_qwen_image_21.json")
REPORT.parent.mkdir(parents=True, exist_ok=True)


class VramSampler:
    def __init__(self, pid: int | None):
        self.pid, self.peak_card, self.peak_proc, self._stop = pid, 0, 0, threading.Event()

    def _read(self):
        card = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                              capture_output=True, text=True).stdout.strip().splitlines()
        apps = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits"],
                              capture_output=True, text=True).stdout.strip().splitlines()
        proc = sum(int(l.split(",")[1]) for l in apps if l and self.pid and int(l.split(",")[0]) == self.pid)
        return int(card[0]) if card else 0, proc

    def run(self):
        while not self._stop.is_set():
            c, p = self._read()
            self.peak_card, self.peak_proc = max(self.peak_card, c), max(self.peak_proc, p)
            time.sleep(0.5)

    def __enter__(self):
        self.t = threading.Thread(target=self.run, daemon=True)
        self.t.start()
        return self

    def __exit__(self, *a):
        self._stop.set()
        self.t.join()


def server_pid() -> int | None:
    out = subprocess.run(["lsof", "-ti", "tcp:8076", "-sTCP:LISTEN"], capture_output=True, text=True).stdout.split()
    return int(out[0]) if out else None


def call(client, **kw):
    args = dict(prompt="", model_label="Turbo (8 steps, fast)", ref_files=[], transparent=False,
                aspect="1:1  · 2048×2048", preview=True, steps=40, seed=1234, randomize=False,
                cfg=1.0, negative="")
    args.update(kw)
    return client.predict(args["prompt"], args["model_label"], args["ref_files"], args["transparent"],
                          args["aspect"], args["preview"], args["steps"], args["seed"], args["randomize"],
                          args["cfg"], args["negative"], api_name="/generate")


def check_png(path: str) -> dict:
    im = Image.open(path)
    info = {"mode": im.mode, "size": im.size, "has_parameters_chunk": "parameters" in im.info}
    if im.mode == "RGBA":
        a = np.asarray(im.getchannel("A"))
        info.update(alpha_min=int(a.min()), alpha_max=int(a.max()),
                    transparent_pct=round(float((a < 16).mean() * 100), 1),
                    opaque_pct=round(float((a > 240).mean() * 100), 1))
    return info


TESTS = {
    "t2i_preview_turbo": dict(prompt='A neon shop sign that reads "SEED 13", rainy night street, reflections on wet pavement, cinematic',
                              preview=True),
    "t2i_preview_base": dict(prompt="A copper dragon perched on a lighthouse at dusk, dramatic sky, oil painting",
                             model_label="Base (full quality, 40 steps)", preview=True, steps=40),
    "t2i_2k_turbo": dict(prompt="A cozy wizard's workshop full of glowing potions and old books, warm lantern light, highly detailed",
                         aspect="16:9 · 2752×1536", preview=False),
    "rgba_turbo": dict(prompt="A cute cartoon purple dragon sticker holding a gold coin", transparent=True,
                       preview=True),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--edit-src", default="")
    a = ap.parse_args()
    only = [s for s in a.only.split(",") if s]
    client = Client(URL, verbose=False)
    report = json.loads(REPORT.read_text()) if REPORT.exists() else {}
    pid = server_pid()
    plan = list(TESTS) + ["edit_turbo"]
    for name in plan:
        if only and name not in only:
            continue
        kw = dict(TESTS.get(name, {}))
        if name == "edit_turbo":
            src = a.edit_src or report.get("t2i_preview_turbo", {}).get("path")
            if not src:
                print("skip edit: no source image")
                continue
            kw = dict(prompt="Change the scene to a snowy winter night; keep the neon sign and its text exactly",
                      ref_files=[handle_file(src)], aspect="Match reference image", preview=True)
        print(f"== {name} ...", flush=True)
        t0 = time.time()
        with VramSampler(pid) as vs:
            path, _gallery, status, seed = call(client, **kw)
        wall = round(time.time() - t0, 1)
        meta = json.loads(Path(path).with_suffix(".json").read_text()) if Path(path).with_suffix(".json").exists() else {}
        real = Path("/home/edq/ai_generated/qwen-image-21") / Path(path).name
        entry = {"path": str(real if real.exists() else path), "wall_s": wall,
                 "gen_s": meta.get("seconds"), "peak_vram_card_mib": vs.peak_card,
                 "peak_vram_server_proc_mib": vs.peak_proc, "status": status, "seed": seed}
        entry["png"] = check_png(entry["path"])
        if not meta:
            side = Path(entry["path"]).with_suffix(".json")
            meta = json.loads(side.read_text()) if side.exists() else {}
        entry["gen_s"] = meta.get("seconds")
        entry["peak_vram_gib_torch"] = meta.get("peak_vram_gib_torch")
        report[name] = entry
        print(json.dumps(entry, indent=1), flush=True)
        REPORT.write_text(json.dumps(report, indent=2))
    print("report:", REPORT)


if __name__ == "__main__":
    main()
