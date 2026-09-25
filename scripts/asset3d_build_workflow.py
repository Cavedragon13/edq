#!/usr/bin/env python3
"""Build the 3D Asset Studio API workflow from ComfyUI's official template.

Source: config/workflows/3d_pixal3d_trellis2_image_to_model.json
        (comfy templates fetch 3d_pixal3d_trellis2_image_to_model)
Output: config/workflows/asset3d_api.json

Needs a running ComfyUI (reads /object_info). Run with venv_comfyui's python:
  venv_comfyui/bin/python scripts/asset3d_build_workflow.py

Changes vs. the template:
  - UI-only Preview3DAdvanced nodes removed; Save3DAdvanced -> SaveGLB (both need a browser viewport).
  - Trellis2UpsampleStage.target_resolution coerced to int (converter leaves '1536').
  - A LoadImageMask(red) node ("900") feeds the "remove background" switch's
    false branch, so the studio's hand-edited mask (white = keep) drives the crop.
    The template wires LoadImage's MASK there, which is 1 - alpha (inverted).
"""
import json
import sys
import urllib.request
from pathlib import Path

from comfy_cli.workflow_to_api import convert_ui_to_api

ROOT = Path("/srv/containers/edq")
SRC = ROOT / "config/workflows/3d_pixal3d_trellis2_image_to_model.json"
OUT = ROOT / "config/workflows/asset3d_api.json"
COMFY = "http://127.0.0.1:8188"

# Template node ids the studio server edits (kept here so a template update
# that renumbers nodes fails loudly at build time, not at generation time).
REQUIRED = {
    "122": "LoadImage",
    "248": "ComfySwitchNode",
    "316": "PrimitiveBoolean",
    "312": "ImageCropToMask",
    "94": "Trellis2UpsampleStage",
    "288": "PrimitiveInt",
    "186": "DecimateMesh",
    "322": "Save3DAdvanced",  # replaced with SaveGLB below
    "3": "KSampler", "12": "KSampler", "18": "KSampler", "23": "KSampler",
}


def main():
    ui = json.loads(SRC.read_text())
    with urllib.request.urlopen(f"{COMFY}/object_info", timeout=60) as r:
        object_info = json.load(r)
    api = convert_ui_to_api(ui, object_info)

    for nid, cls in REQUIRED.items():
        got = api.get(nid, {}).get("class_type")
        if got != cls:
            sys.exit(f"template changed: node {nid} is {got!r}, expected {cls!r}")

    for nid in [k for k, v in api.items() if v["class_type"] == "Preview3DAdvanced"]:
        del api[nid]

    api["94"]["inputs"]["target_resolution"] = int(api["94"]["inputs"]["target_resolution"])

    # Save3DAdvanced needs a browser viewport_state; SaveGLB saves the same
    # final textured file server-side.
    api["322"] = {
        "class_type": "SaveGLB",
        "inputs": {"mesh": api["322"]["inputs"]["model_3d"], "filename_prefix": "asset3d/model"},
        "_meta": {"title": "Save GLB (studio)"},
    }

    api["900"] = {
        "class_type": "LoadImageMask",
        "inputs": {"image": "asset3d_mask.png", "channel": "red"},
        "_meta": {"title": "Studio mask (white = keep)"},
    }
    api["248"]["inputs"]["on_false"] = ["900", 0]
    api["248"]["inputs"]["switch"] = False

    OUT.write_text(json.dumps(api, indent=2))
    print(f"wrote {OUT} ({len(api)} nodes)")


if __name__ == "__main__":
    main()
