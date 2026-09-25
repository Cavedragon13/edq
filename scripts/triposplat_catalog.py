#!/usr/bin/env python3
"""Catalog TripoSplat outputs: previews next to each splat, and source-image matching.

TripoSplat (Pinokio app) writes ~/ai_generated/triposplat/<random12>/splat.ply and
discards the input image, so folders can't be told apart. This tool:

  previews                 write preview.png (front | side | back) into every splat
                           folder that doesn't have one yet (--force to redo)
  match IMAGE [IMAGE ...]  rank splats by how well their front view matches each
                           source image; best match first

Splat axes are OpenCV-style: Y points down, and the input-image view looks from +X
toward -X (screen right = +Z). Verified on the witch splat f8362d281d3a, 2026-09-23.

Usage:
  python3 scripts/triposplat_catalog.py previews
  python3 scripts/triposplat_catalog.py match ~/Downloads/witch.png
"""
import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path("/home/edq/ai_generated/triposplat")
SH_C0 = 0.28209479
OPACITY_MIN = 0.3
BG = np.array([0.15, 0.15, 0.15])


def load_splat(ply: Path):
    raw = ply.read_bytes()
    header_end = raw.index(b"end_header\n") + len(b"end_header\n")
    header = raw[:header_end].decode("ascii", "replace").splitlines()
    props = [line.split()[-1] for line in header if line.startswith("property")]
    a = np.frombuffer(raw[header_end:], dtype="<f4").reshape(-1, len(props))
    col = {p: i for i, p in enumerate(props)}
    op = 1.0 / (1.0 + np.exp(-a[:, col["opacity"]]))
    keep = op > OPACITY_MIN
    xyz = a[keep][:, [col["x"], col["y"], col["z"]]]
    rgb = np.clip(0.5 + SH_C0 * a[keep][:, [col["f_dc_0"], col["f_dc_1"], col["f_dc_2"]]], 0, 1)
    return xyz, rgb


def render(xyz, rgb, view: str, size: int = 256):
    """Orthographic z-buffered point render. Returns (rgb float image, coverage mask)."""
    x, y, z = xyz[:, 0], xyz[:, 1], xyz[:, 2]
    # (screen-right, screen-down, depth toward camera)
    h, v, depth = {
        "front": (z, y, x),
        "back": (-z, y, -x),
        "side": (-x, y, z),
    }[view]
    lo = min(h.min(), v.min())
    span = max(h.max(), v.max()) - lo
    margin = 4
    scale = (size - 1 - 2 * margin) / span
    u = ((h - lo) * scale + margin).astype(int)
    w = ((v - lo) * scale + margin).astype(int)
    img = np.tile(BG, (size, size, 1))
    mask = np.zeros((size, size), bool)
    order = np.argsort(depth)  # nearest to camera painted last
    img[w[order], u[order]] = rgb[order]
    mask[w, u] = True
    # close pinholes between points
    pil = Image.fromarray((img * 255).astype(np.uint8))
    filled = np.asarray(pil.filter(ImageFilter.MedianFilter(3))) / 255.0
    img = np.where(mask[..., None], img, filled)
    mask = np.asarray(Image.fromarray(mask).filter(ImageFilter.MaxFilter(3)))
    return img, mask


def write_preview(ply: Path) -> Path:
    """Write preview.png (front | side | back) next to one splat.ply."""
    out = ply.parent / "preview.png"
    xyz, rgb = load_splat(ply)
    tiles = [render(xyz, rgb, view, 384)[0] for view in ("front", "side", "back")]
    Image.fromarray((np.concatenate(tiles, 1) * 255).astype(np.uint8)).save(out)
    return out


def write_previews(force: bool):
    made = 0
    for ply in sorted(ROOT.glob("*/splat.ply")):
        if (ply.parent / "preview.png").exists() and not force:
            continue
        print(f"wrote {write_preview(ply)}")
        made += 1
    print(f"{made} preview(s) written")


def _crop_norm(img, mask, n=64):
    ys, xs = np.nonzero(mask)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    side = max(y1 - y0, x1 - x0)
    cy, cx = (y0 + y1) // 2, (x0 + x1) // 2
    pad = side // 2 + 1
    im = np.pad(img, ((pad, pad), (pad, pad), (0, 0)), constant_values=0)
    mk = np.pad(mask, ((pad, pad), (pad, pad)), constant_values=False)
    cy, cx = cy + pad, cx + pad
    half = side // 2
    im = im[cy - half:cy + half, cx - half:cx + half]
    mk = mk[cy - half:cy + half, cx - half:cx + half]
    im = np.asarray(Image.fromarray((im * 255).astype(np.uint8)).resize((n, n), Image.BILINEAR)) / 255.0
    mk = np.asarray(Image.fromarray(mk.astype(np.uint8) * 255).resize((n, n), Image.BILINEAR)) > 127
    return im, mk


def source_foreground(path: Path):
    """Source image + foreground mask (alpha if present, else distance from border color)."""
    pil = Image.open(path).convert("RGBA")
    pil.thumbnail((512, 512))
    arr = np.asarray(pil) / 255.0
    rgb, alpha = arr[..., :3], arr[..., 3]
    if alpha.min() < 0.5:
        mask = alpha > 0.5
    else:
        border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
        bg = np.median(border, axis=0)
        mask = np.linalg.norm(rgb - bg, axis=2) > 0.12
    return rgb, mask


def score(src_img, src_mask, splat_img, splat_mask):
    a_img, a_mk = _crop_norm(src_img, src_mask)
    b_img, b_mk = _crop_norm(splat_img, splat_mask)
    union = a_mk | b_mk
    iou = (a_mk & b_mk).sum() / max(1, union.sum())
    both = a_mk & b_mk
    color_err = np.linalg.norm(a_img[both] - b_img[both], axis=1).mean() if both.any() else 1.0
    return iou - color_err, iou, color_err


def match(images):
    splats = []
    for ply in sorted(ROOT.glob("*/splat.ply")):
        xyz, rgb = load_splat(ply)
        img, mask = render(xyz, rgb, "front", 256)
        splats.append((ply.parent.name, img, mask))
    for path in images:
        src_img, src_mask = source_foreground(Path(path))
        ranked = sorted(((score(src_img, src_mask, im, mk), name) for name, im, mk in splats), reverse=True)
        print(f"\n{path}")
        print("  score    iou  color_err  folder")
        for (s, iou, err), name in ranked[:5]:
            print(f"  {s:+.3f}  {iou:.3f}  {err:.3f}      {ROOT / name}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("previews")
    p.add_argument("--force", action="store_true", help="regenerate existing previews")
    m = sub.add_parser("match")
    m.add_argument("images", nargs="+")
    args = ap.parse_args()
    if args.cmd == "previews":
        write_previews(args.force)
    else:
        match(args.images)


if __name__ == "__main__":
    sys.exit(main())
