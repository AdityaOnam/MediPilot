#!/usr/bin/env python3
"""
cutout.py — prepare MediPilot mascot art for the web app.

Google Flow / Nano Banana export opaque PNGs on a flat background. The app needs
transparent PNGs so the mascot can sit on the warm paper surface, the dark
clinical surface, or a video. This does two jobs:

  1. split   — cut a 4x2 (or NxM) pose sheet into individual pose PNGs
  2. cut     — flood-fill the flat background away from the corners, leaving the
               character (and its white eyes, which a naive "remove white"
               would destroy) intact

Usage
-----
  python cutout.py split pose-sheet.png --cols 4 --rows 2 --out poses/
  python cutout.py cut   poses/*.png --out cutouts/
  python cutout.py cut   listening.png --shadow --out cutouts/

Flags
-----
  --tol N       colour distance tolerance for the flood fill (default 26)
  --shadow      second looser pass to also remove the soft grey ground shadow
  --feather N   pixels of alpha ramp at the edge, kills white fringing (default 1)
  --pad N       padding kept around the character when auto-cropping (default 12)
  --no-crop     keep the original canvas size instead of cropping to the subject

Requires: pillow, numpy
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
from collections import deque

import numpy as np
from PIL import Image


def flood_background(rgb: np.ndarray, tol: float) -> np.ndarray:
    """Return a boolean mask of background pixels, grown inward from the corners.

    Corner-seeded rather than colour-keyed on purpose: the mascot's eyes are the
    same white as the backdrop, and a global key would punch holes in its face.
    """
    h, w, _ = rgb.shape
    bg = np.zeros((h, w), dtype=bool)
    seen = np.zeros((h, w), dtype=bool)
    q: deque[tuple[int, int]] = deque()

    for y, x in ((0, 0), (0, w - 1), (h - 1, 0), (h - 1, w - 1)):
        if not seen[y, x]:
            seen[y, x] = True
            q.append((y, x))

    seeds = np.array([rgb[0, 0], rgb[0, w - 1], rgb[h - 1, 0], rgb[h - 1, w - 1]], dtype=np.int16)
    ref = seeds.mean(axis=0)

    while q:
        y, x = q.popleft()
        if np.abs(rgb[y, x].astype(np.int16) - ref).max() > tol:
            continue
        bg[y, x] = True
        for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if 0 <= ny < h and 0 <= nx < w and not seen[ny, nx]:
                seen[ny, nx] = True
                q.append((ny, nx))
    return bg


def feather(alpha: np.ndarray, px: int) -> np.ndarray:
    """Soften the alpha edge so the black outline doesn't keep a white halo."""
    if px <= 0:
        return alpha
    a = alpha.astype(np.float32)
    for _ in range(px):
        p = np.pad(a, 1, mode="edge")
        a = np.minimum(
            a,
            (p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:] + a * 4) / 8.0,
        )
    return a.astype(np.uint8)


def cut_one(path: str, out_dir: str, tol: int, shadow: bool, fpx: int, pad: int, crop: bool) -> str:
    im = Image.open(path).convert("RGB")
    rgb = np.asarray(im)

    bg = flood_background(rgb, tol)
    if shadow:
        # A soft drop shadow is a light, desaturated ramp continuous with the
        # backdrop, so a second looser pass reaches it without touching flat art.
        bg |= flood_background(rgb, tol * 2.6)

    alpha = np.where(bg, 0, 255).astype(np.uint8)
    alpha = feather(alpha, fpx)

    out = np.dstack([rgb, alpha])
    img = Image.fromarray(out, mode="RGBA")

    if crop:
        ys, xs = np.where(alpha > 8)
        if len(ys):
            y0, y1 = max(0, ys.min() - pad), min(img.height, ys.max() + pad + 1)
            x0, x1 = max(0, xs.min() - pad), min(img.width, xs.max() + pad + 1)
            img = img.crop((x0, y0, x1, y1))

    os.makedirs(out_dir, exist_ok=True)
    dest = os.path.join(out_dir, os.path.splitext(os.path.basename(path))[0] + ".png")
    img.save(dest)
    kept = int((alpha > 8).sum()) * 100 // alpha.size
    print(f"  {os.path.basename(path)} -> {dest}  ({img.width}x{img.height}, {kept}% opaque)")
    return dest


def split_sheet(path: str, cols: int, rows: int, out_dir: str) -> None:
    im = Image.open(path).convert("RGB")
    w, h = im.size
    cw, ch = w // cols, h // rows
    os.makedirs(out_dir, exist_ok=True)
    n = 0
    for r in range(rows):
        for c in range(cols):
            n += 1
            tile = im.crop((c * cw, r * ch, (c + 1) * cw, (r + 1) * ch))
            dest = os.path.join(out_dir, f"pose-{n:02d}.png")
            tile.save(dest)
            print(f"  pose-{n:02d}.png  ({cw}x{ch})")
    print(f"\n{n} poses written to {out_dir}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("split", help="cut a pose sheet into individual poses")
    sp.add_argument("path")
    sp.add_argument("--cols", type=int, default=4)
    sp.add_argument("--rows", type=int, default=2)
    sp.add_argument("--out", default="poses")

    cu = sub.add_parser("cut", help="make the flat background transparent")
    cu.add_argument("paths", nargs="+")
    cu.add_argument("--out", default="cutouts")
    cu.add_argument("--tol", type=int, default=26)
    cu.add_argument("--shadow", action="store_true", help="also remove the soft ground shadow")
    cu.add_argument("--feather", type=int, default=1)
    cu.add_argument("--pad", type=int, default=12)
    cu.add_argument("--no-crop", dest="crop", action="store_false")

    a = ap.parse_args()

    if a.cmd == "split":
        split_sheet(a.path, a.cols, a.rows, a.out)
        return 0

    files: list[str] = []
    for p in a.paths:
        files.extend(glob.glob(p))
    if not files:
        print("no files matched", file=sys.stderr)
        return 1

    print(f"cutting {len(files)} file(s), tol={a.tol}, shadow={a.shadow}")
    for f in sorted(files):
        cut_one(f, a.out, a.tol, a.shadow, a.feather, a.pad, a.crop)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
