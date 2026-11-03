#!/usr/bin/env python3
"""Regenerate figures/domain_schematic.png: a 2x2 schematic of the four
fin-series domain/body configurations used in the report --
  (a) periodic z, no fins       (faster_nofin_full_span)
  (b) wall z, no fins           (faster_nofin_large)
  (c) periodic z, one fin       (faster_midfin)
  (d) periodic z, two fins      (faster_2fin)

    module load anaconda3/2025.06
    python3 reports/3d_preliminary/scripts/domain_schematic.py
"""
import tempfile
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from PIL import Image

OUT_DIR = Path(__file__).resolve().parent.parent / "figures"

# Physical domain, shared by both z-boundary settings: x in [-30,120]
# (streamwise), y in [-120,30] (vertical, gravity-aligned), z in
# [-17.5,17.5] (spanwise, the cylinder axis).
X0, X1 = -30.0, 120.0
Y0, Y1 = -120.0, 30.0
Z0, Z1 = -17.5, 17.5
R = 3.17
FIN_R = 6.34  # fin radius (= 2R), per geometry.json for faster_midfin / faster_2fin


def P(xp, yp, zp):
    """Swap physical y <-> z for plotting, so phys-y (gravity-aligned) renders
    as mplot3d's vertical axis: plot-x = phys x, plot-y = phys z (depth),
    plot-z = phys y (up)."""
    return (xp, zp, yp)


def line3d(ax, p0, p1, **kw):
    ax.plot([p0[0], p1[0]], [p0[1], p1[1]], [p0[2], p1[2]], **kw)


def draw_panel(ax, periodic, fin_fracs=(), title=""):
    corners = np.array([P(x, y, z) for x in (X0, X1) for y in (Y0, Y1) for z in (Z0, Z1)])

    def face(pts_idx):
        return [corners[i] for i in pts_idx]

    side_faces = [
        face([0, 1, 3, 2]),  # x = X0
        face([4, 5, 7, 6]),  # x = X1
        face([0, 1, 5, 4]),  # y = Y0
        face([2, 3, 7, 6]),  # y = Y1
    ]
    z_faces = [
        face([0, 2, 6, 4]),  # z = Z0
        face([1, 3, 7, 5]),  # z = Z1
    ]
    # x and y are always solid walls (never periodic in this case suite) --
    # render them opaque blue. z is either a wall too (solid blue, same as
    # x/y) or periodic (no face at all, transparent -- just the dashed
    # depth edges below). edgecolor="none": face outlines are drawn
    # separately below (solid or dashed per edge) -- a Poly3DCollection
    # edgecolor would draw its own solid outline on top and hide the
    # dashing on the depth edges.
    WALL_ALPHA = 0.35
    ax.add_collection3d(Poly3DCollection(side_faces, facecolor="tab:blue",
                                          edgecolor="none", alpha=WALL_ALPHA))
    if not periodic:
        ax.add_collection3d(Poly3DCollection(z_faces, facecolor="tab:blue",
                                              edgecolor="none", alpha=WALL_ALPHA))

    edges = [
        (0, 1), (0, 2), (0, 4), (1, 3), (1, 5), (2, 3),
        (2, 6), (3, 7), (4, 5), (4, 6), (5, 7), (6, 7),
    ]
    z_edges = {(0, 1), (2, 3), (4, 5), (6, 7)}  # pure depth-direction edges (differ only in z)
    for e in edges:
        i, j = e
        p, q = corners[i], corners[j]
        if periodic and e in z_edges:
            line3d(ax, p, q, color="k", lw=0.8, ls=(0, (3, 2)))
        else:
            line3d(ax, p, q, color="k", lw=0.8)

    # --- cylinder ---
    if periodic:
        cyl_z0, cyl_z1 = Z0, Z1
    else:
        L = 25.5
        cyl_z0, cyl_z1 = -L / 2, L / 2

    theta = np.linspace(0, 2 * np.pi, 48)
    zline = np.linspace(cyl_z0, cyl_z1, 2)
    theta_grid, z_grid = np.meshgrid(theta, zline)
    xp = R * np.cos(theta_grid)
    yp = R * np.sin(theta_grid)
    px, py, pz = P(xp, yp, z_grid)
    ax.plot_surface(px, py, pz, color="firebrick", alpha=0.85,
                     linewidth=0, antialiased=True, shade=True)
    for zc in (cyl_z0, cyl_z1):
        r = np.linspace(0, R, 2)
        rg, tg = np.meshgrid(r, theta)
        xc = rg * np.cos(tg)
        yc = rg * np.sin(tg)
        zc_arr = np.full_like(xc, zc)
        pxc, pyc, pzc = P(xc, yc, zc_arr)
        ax.plot_surface(pxc, pyc, pzc, color="firebrick", alpha=0.85, linewidth=0)

    # --- fins: thin disks of radius FIN_R, perpendicular to the cylinder
    # axis, at the given z-fractions (0 = Z0, 1 = Z1), per geometry.json ---
    for frac in fin_fracs:
        zc = Z0 + frac * (Z1 - Z0)
        r = np.linspace(0, FIN_R, 2)
        rg, tg = np.meshgrid(r, theta)
        xc = rg * np.cos(tg)
        yc = rg * np.sin(tg)
        zc_arr = np.full_like(xc, zc)
        pxc, pyc, pzc = P(xc, yc, zc_arr)
        ax.plot_surface(pxc, pyc, pzc, color="darkorange", alpha=0.75, linewidth=0)

    ax.scatter(*P(0, 0, 0), color="k", s=20, depthshade=False)

    # --- coordinate triad, anchored outside the (X0,Y0,Z0) corner. The
    # anchor sits well before Z0 in depth so the +z shaft, even after
    # advancing by arrow_len, still ends short of the box's own z-span --
    # it never visually crosses the domain wireframe. ---
    ox, oy, oz = X0 - 22, Y0 - 22, Z0 - 30
    arrow_len = 25
    o = P(ox, oy, oz)
    line3d(ax, o, P(ox + arrow_len, oy, oz), color="k", lw=1.5)
    line3d(ax, o, P(ox, oy + arrow_len, oz), color="k", lw=1.5)
    line3d(ax, o, P(ox, oy, oz + arrow_len), color="k", lw=1.5)
    ax.text(*P(ox + arrow_len + 5, oy, oz), "$x$", fontsize=12)
    ax.text(*P(ox, oy + arrow_len + 5, oz), "$y$", fontsize=12)
    ax.text(*P(ox, oy, oz + arrow_len + 5), "$z$", fontsize=12)

    # --- gravity arrow ---
    gx, gy, gz = X1 - 35, Y1 - 10, Z1 - 5
    g_tip = P(gx, gy - 24, gz)
    line3d(ax, P(gx, gy, gz), g_tip, color="tab:gray", lw=2.2)
    ax.scatter(*g_tip, color="tab:gray", marker="v", s=260, depthshade=False,
               edgecolors="none")
    ax.text(*P(gx + 3, gy - 30, gz), r"$g_{\mathrm{eff}}$", color="tab:gray", fontsize=12)

    # --- domain extent labels ---
    ax.text(*P((X0 + X1) / 2, Y0 - 14, Z0), f"$x \\in [{X0:.0f}, {X1:.0f}]$",
            color="tab:blue", fontsize=10, ha="center")
    ax.text(*P(X1 + 10, (Y0 + Y1) / 2, Z0), f"$y \\in [{Y0:.0f}, {Y1:.0f}]$\n(vertical)",
            color="tab:blue", fontsize=10, ha="left", va="center")
    z_tag = "(periodic)" if periodic else "(wall)"
    ax.text(*P(X0 - 8, Y1 + 10, (Z0 + Z1) / 2), f"$z \\in [{Z0:.1f}, {Z1:.1f}]$\n{z_tag}",
            color="tab:blue", fontsize=10, ha="right")

    ax.set_box_aspect((X1 - X0, (Z1 - Z0) * 2.2, Y1 - Y0))
    ax.view_init(elev=20, azim=-60)
    ax.set_axis_off()
    ax.set_title(title, fontsize=15)


def render_panel(path, **kwargs):
    fig = plt.figure(figsize=(8, 7))
    ax = fig.add_subplot(111, projection="3d")
    draw_panel(ax, **kwargs)
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def autocrop(path, pad=20):
    im = Image.open(path).convert("RGB")
    arr = np.array(im)
    non_white = np.any(arr < 250, axis=2)
    ys, xs = np.where(non_white)
    x0, x1 = max(xs.min() - pad, 0), min(xs.max() + pad, arr.shape[1])
    y0, y1 = max(ys.min() - pad, 0), min(ys.max() + pad, arr.shape[0])
    im.crop((x0, y0, x1, y1)).save(path)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        panels = [
            (f"{tmp}/panel_a.png", dict(periodic=True, title="(a) Periodic $z$, no fins")),
            (f"{tmp}/panel_b.png", dict(periodic=False, title="(b) Wall $z$, no fins")),
            (f"{tmp}/panel_c.png", dict(periodic=True, fin_fracs=[0.5], title="(c) Periodic $z$, one fin")),
            (f"{tmp}/panel_d.png", dict(periodic=True, fin_fracs=[0.25, 0.75], title="(d) Periodic $z$, two fins")),
        ]
        for path, kwargs in panels:
            render_panel(path, **kwargs)
            autocrop(path)

        imgs = [Image.open(p) for p, _ in panels]
        cell_w = max(im.width for im in imgs)
        cell_h = max(im.height for im in imgs)
        gap = 40
        grid = Image.new("RGB", (cell_w * 2 + gap, cell_h * 2 + gap), "white")
        positions = [(0, 0), (cell_w + gap, 0), (0, cell_h + gap), (cell_w + gap, cell_h + gap)]
        for im, (px, py) in zip(imgs, positions):
            # center each panel within its cell
            ox = px + (cell_w - im.width) // 2
            oy = py + (cell_h - im.height) // 2
            grid.paste(im, (ox, oy))

        out_path = OUT_DIR / "domain_schematic.png"
        grid.save(out_path)
        print("Saved", out_path, grid.size)


if __name__ == "__main__":
    main()
