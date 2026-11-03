#!/usr/bin/env python3
"""Crop the omega_z iso-surface renders (from tools/render_isosurface.py)
used in the report's "Flow structure" figures, and erase the VisIt axis
triad overlay without cutting into shaded surface detail.

Brightness alone can't separate the triad from surface shading: shaded
facets on the red/green isosurface legitimately get nearly as dark as true
black, so a plain "near black" mask cuts thin cracks through the mesh.
Hue survives shading (a dark-shaded red facet still has R > G, B) while the
triad is neutral gray/black (R ~ G ~ B), so hue dominance identifies real
surface at any brightness; the triad is then only the neutral pixels that
sit away from any colored surface (open white space), which keeps thin
anti-aliasing seams between facets intact.

    module load anaconda3/2025.06
    python3 reports/3d_preliminary/scripts/crop_vorticity_figs.py

Source renders live in cases/figures/ on the real project scratch
directory (not part of this git repo -- see tools/render_isosurface.py).
"""
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

SRC_DIR = Path("/scratch/sc7825/3dRotatingCylinder/cases/figures")
OUT_DIR = Path(__file__).resolve().parent.parent / "figures"

MIN_BLOB_PIXELS = 1500  # drop stray render-noise fragments smaller than this
PAD = 30

NAMES = [
    "faster_nofin_full_span_omega_z_t22_tube",
    "faster_nofin_full_span_omega_z_t22_front",
    "faster_midfin_omega_z_t22_tube",
    "faster_midfin_omega_z_t22_front",
    "faster_2fin_omega_z_t22_tube",
    "faster_2fin_omega_z_t22_front",
]


def crop_one(name):
    im = Image.open(SRC_DIR / f"{name}.png").convert("RGB")
    arr = np.array(im)
    r, g, b = arr[..., 0].astype(int), arr[..., 1].astype(int), arr[..., 2].astype(int)

    reddish = (r > g + 15) & (r > b + 15)
    greenish = (g > r + 15) & (g > b + 15)
    colored = reddish | greenish
    white = np.all(arr > 250, axis=2)
    neutral = ~colored & ~white  # candidate triad / AA-blend pixels

    # Only erase neutral pixels that sit away from any colored surface --
    # this keeps thin anti-aliasing seams between facets intact and only
    # wipes the triad, which sits in open white space.
    colored_dilated = ndimage.binary_dilation(colored, iterations=20)
    triad_mask = neutral & ~colored_dilated

    content_mask = colored  # used for bbox + blob-size filtering
    labeled, n = ndimage.label(content_mask)
    sizes = ndimage.sum(content_mask, labeled, range(1, n + 1))
    keep = np.zeros_like(content_mask)
    for i, s in enumerate(sizes, start=1):
        if s >= MIN_BLOB_PIXELS:
            keep |= labeled == i

    ys, xs = np.where(keep)
    x0, x1 = max(xs.min() - PAD, 0), min(xs.max() + PAD, arr.shape[1])
    y0, y1 = max(ys.min() - PAD, 0), min(ys.max() + PAD, arr.shape[0])

    clean = arr.copy()
    clean[triad_mask] = 255
    out = Image.fromarray(clean).crop((x0, y0, x1, y1))
    out_path = OUT_DIR / f"{name}.png"
    out.save(out_path)
    print(name, "->", out.size, "bbox", (x0, y0, x1, y1))


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name in NAMES:
        crop_one(name)


if __name__ == "__main__":
    main()
