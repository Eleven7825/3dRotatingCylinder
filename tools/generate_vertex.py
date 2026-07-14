#!/usr/bin/env python3
"""
generate_vertex.py — generate the IB point cloud for a cylinder case.

Reads a case's geometry.json and writes cylinder3d.vertex + indices next to it.

    python3 tools/generate_vertex.py cases/faster_nofin
    python3 tools/generate_vertex.py cases/faster_nofin --check

Geometry model
--------------
The body is a solid cylinder of radius `Radius` and length `L`, discretized on
the *finest* Eulerian grid (dx = Lx/Nx, etc. — these must match the finest level
of input3d, or the IB points will not be one-per-cell).

Points are laid down layer by layer along z. Every layer is a disc of radius `a`:

    use_disk = 0            every layer uses a = Radius            (bare cylinder)
    use_disk = 1            total_disks equally spaced layers are widened:
                              - the first and last are end caps,  a = endCap_radius
                              - any layers in between are fins,   a = disk_radius
                            all other layers use a = Radius

The cloud is recentered on its own center of mass before being written.

indices
-------
Cumulative (0-based) index of the last point of each widened layer, plus the
first and last layer. Not read by the solver — it is a bookkeeping aid for
identifying end-cap / fin points in post-processing.
"""

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

REQUIRED_KEYS = {
    "mesh": ["Lx", "Ly", "Lz", "Nx", "Ny", "Nz"],
    "cylinder": ["X_com", "Y_com", "Z_com", "Radius", "L",
                 "use_disk", "total_disks", "disk_radius", "endCap_radius"],
}


def load_geometry(case_dir: Path) -> dict:
    path = case_dir / "geometry.json"
    if not path.exists():
        sys.exit(f"ERROR: no geometry.json in {case_dir}")
    geom = json.loads(path.read_text())
    for section, keys in REQUIRED_KEYS.items():
        if section not in geom:
            sys.exit(f"ERROR: {path}: missing section '{section}'")
        missing = [k for k in keys if k not in geom[section]]
        if missing:
            sys.exit(f"ERROR: {path}: section '{section}' missing keys: {missing}")
    return geom


def marked_layers(use_disk: int, total_disks: int, num_pts_z: int):
    """Return (endcap_layers, fin_layers) as 1-based z-layer indices."""
    if not use_disk:
        return [], []
    if total_disks >= 2:
        # Equally spaced across the full length, first and last are the end caps.
        spacing = (num_pts_z - 1) / (total_disks - 1)
        layers = [int(round(1 + i * spacing)) for i in range(total_disks)]
        return [layers[0], layers[-1]], layers[1:-1]
    return [1, num_pts_z], []


def build(geom: dict):
    m, c = geom["mesh"], geom["cylinder"]

    dx = m["Lx"] / m["Nx"]
    dy = m["Ly"] / m["Ny"]
    dz = m["Lz"] / m["Nz"]

    Radius = c["Radius"]
    endCap_radius = c["endCap_radius"]
    disk_radius = c["disk_radius"]
    X_com, Y_com, Z_com = c["X_com"], c["Y_com"], c["Z_com"]

    # Loop bounds are sized off the widest possible disc so every layer fits.
    num_pts_x = math.ceil(2 * endCap_radius / dx)
    num_pts_y = math.ceil(2 * endCap_radius / dy)
    num_pts_z = math.ceil(c["L"] / dz)

    endcaps, fins = marked_layers(c["use_disk"], c["total_disks"], num_pts_z)

    X, Y, Z = [], [], []
    idx = 0
    index_marks = []

    for k in range(1, num_pts_z + 1):
        z = Z_com + ((k - 1) * dz - m["Lz"] / 2)

        if k in endcaps:
            a = endCap_radius
        elif k in fins:
            a = disk_radius
        else:
            a = Radius

        # Discs are anchored at -a, so the point lattice shifts with the radius.
        i = np.arange(num_pts_x)
        j = np.arange(num_pts_y)
        x = X_com + (i * dx - a)
        y = Y_com + (j * dy - a)
        xx, yy = np.meshgrid(x, y, indexing="ij")
        inside = ((xx - X_com) ** 2 + (yy - Y_com) ** 2) <= a ** 2

        xs, ys = xx[inside], yy[inside]
        X.append(xs)
        Y.append(ys)
        Z.append(np.full(xs.shape, z))
        idx += xs.size

        if k in endcaps or k in fins or k == 1 or k == num_pts_z:
            index_marks.append(idx - 1)

    X = np.concatenate(X)
    Y = np.concatenate(Y)
    Z = np.concatenate(Z)

    X -= X.sum() / X.size
    Y -= Y.sum() / Y.size
    Z -= Z.sum() / Z.size

    info = {
        "dx": (dx, dy, dz),
        "layers": num_pts_z,
        "endcaps": endcaps,
        "fins": fins,
        "npoints": X.size,
    }
    return X, Y, Z, sorted(set(index_marks)), info


def write_vertex(path: Path, X, Y, Z):
    with open(path, "w") as f:
        f.write(f"{X.size}\n")
        for x, y, z in zip(X, Y, Z):
            f.write(f"{x:.6f}\t{y:.6f}\t{z:.6f}\n")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("case_dir", type=Path, help="case directory containing geometry.json")
    p.add_argument("--check", action="store_true",
                   help="regenerate into memory and compare against the existing "
                        "cylinder3d.vertex instead of overwriting it")
    args = p.parse_args()

    case_dir = args.case_dir.resolve()
    geom = load_geometry(case_dir)

    X, Y, Z, marks, info = build(geom)

    dx, dy, dz = info["dx"]
    print(f"case        : {case_dir.name}")
    print(f"grid spacing: dx={dx:g} dy={dy:g} dz={dz:g}")
    print(f"z-layers    : {info['layers']}")
    print(f"end caps    : {info['endcaps'] or 'none'}")
    print(f"fins        : {info['fins'] or 'none'}")
    print(f"points      : {info['npoints']}")

    vertex = case_dir / "cylinder3d.vertex"

    if args.check:
        if not vertex.exists():
            sys.exit(f"ERROR: --check but {vertex} does not exist")
        tmp = vertex.with_suffix(".vertex.check")
        write_vertex(tmp, X, Y, Z)
        same = tmp.read_bytes() == vertex.read_bytes()
        tmp.unlink()
        print("check       : MATCH" if same else "check       : MISMATCH")
        sys.exit(0 if same else 1)

    write_vertex(vertex, X, Y, Z)
    (case_dir / "indices").write_text("".join(f"{n}\n" for n in marks))
    print(f"wrote       : {vertex.name}, indices")


if __name__ == "__main__":
    main()
