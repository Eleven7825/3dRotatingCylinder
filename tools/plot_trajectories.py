#!/usr/bin/env python3
"""Regenerate cases/trajectory_comparison.png from the latest run of each case.

    module load anaconda3/2025.06
    python3 tools/plot_trajectories.py

For each case under cases/, finds the most recent runs/<case>_<stamp>/ folder
that has produced output and plots its center_of_mass trajectory. Must run on
a login node (reads from /archive) with IBAMR_SCRATCH_DIR set if runs/ isn't
under PROJECT_DIR/runs (see README "Torch note").
"""

import argparse
import os
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PROJECT_DIR = Path(__file__).resolve().parent.parent
CASES_DIR = PROJECT_DIR / "cases"

_scratch_env = os.environ.get("IBAMR_SCRATCH_DIR", "")
SCRATCH_DIR = Path(_scratch_env).resolve() if _scratch_env else PROJECT_DIR
RUNS_DIR = SCRATCH_DIR / "runs"

# Computational domain / reference-domain boxes — kept in sync with the note
# in cases/README.md. Always drawn: it's the frame every COM trajectory is
# judged against (did the body exit the domain, how close to the boundary).
DOMAIN_BOX = {"x": (-30, 120), "y": (-120, 30)}
REFERENCE_BOX = {"x": (-20, 80), "y": (-27, 18)}

TIME_RE = re.compile(r"^Simulation time is\s+([-\d.eE+]+)")
COM_RE = re.compile(r"^center_of_mass:\s+([-\d.eE+]+)\s+([-\d.eE+]+)")


def list_cases():
    return sorted(d.name for d in CASES_DIR.iterdir()
                  if d.is_dir() and (d / "input3d").exists())


def latest_run_with_output(case):
    """Most recent runs/<case>_<stamp>/ that has a non-empty .out file."""
    pattern = re.compile(rf"^{re.escape(case)}_\d{{4}}-\d{{2}}-\d{{2}}_\d{{2}}-\d{{2}}-\d{{2}}$")
    if not RUNS_DIR.is_dir():
        return None
    candidates = sorted(
        (d for d in RUNS_DIR.iterdir() if d.is_dir() and pattern.match(d.name)),
        key=lambda d: d.name, reverse=True,
    )
    for run_dir in candidates:
        for out_file in sorted(run_dir.glob("ibamr-rotating-cylinder-*.out")):
            if out_file.stat().st_size > 0:
                return out_file
    return None


def extract_trajectory(path, stride=20):
    """Sample every `stride`-th (t, x, y) COM point to keep plotting fast."""
    t_cur = None
    ts, xs, ys = [], [], []
    i = 0
    with open(path, "r", errors="ignore") as f:
        for line in f:
            m = TIME_RE.match(line)
            if m:
                t_cur = float(m.group(1))
                continue
            m = COM_RE.match(line)
            if m and t_cur is not None:
                i += 1
                if i % stride == 0:
                    ts.append(t_cur)
                    xs.append(float(m.group(1)))
                    ys.append(float(m.group(2)))
                t_cur = None
    return ts, xs, ys


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", default=str(CASES_DIR / "trajectory_comparison.png"),
                   help="output PNG path (default: cases/trajectory_comparison.png)")
    p.add_argument("--stride", type=int, default=20,
                   help="plot every Nth logged COM point (default: 20)")
    args = p.parse_args()

    cases = list_cases()
    data = {}
    for case in cases:
        out_file = latest_run_with_output(case)
        if out_file is None:
            print(f"{case}: no run output found, skipping")
            continue
        ts, xs, ys = extract_trajectory(out_file, stride=args.stride)
        if not ts:
            print(f"{case}: {out_file} has no COM data yet, skipping")
            continue
        data[case] = (ts, xs, ys)
        print(f"{case}: {out_file.parent.name} — {len(ts)} points, "
              f"t_end={ts[-1]:.4g}, final=({xs[-1]:.4g},{ys[-1]:.4g})")

    fig, ax = plt.subplots(figsize=(10, 8))
    cmap = plt.get_cmap("tab10")
    for i, (case, (ts, xs, ys)) in enumerate(data.items()):
        color = cmap(i % 10)
        ax.plot(xs, ys, "-", color=color, label=case, linewidth=1.6, alpha=0.85)
        ax.plot(xs[0], ys[0], "o", color=color, markersize=5)
        ax.plot(xs[-1], ys[-1], "s", color=color, markersize=6)

    dx, dy = DOMAIN_BOX["x"], DOMAIN_BOX["y"]
    ax.plot([dx[0], dx[1], dx[1], dx[0], dx[0]],
            [dy[0], dy[0], dy[1], dy[1], dy[0]],
            "r--", linewidth=1.5, label="computational domain")

    rx, ry = REFERENCE_BOX["x"], REFERENCE_BOX["y"]
    ax.plot([rx[0], rx[1], rx[1], rx[0], rx[0]],
            [ry[0], ry[0], ry[1], ry[1], ry[0]],
            ":", color="purple", linewidth=1.5, label="100x45 reference domain")

    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_title("Center-of-mass trajectories (circle=start, square=end/last-logged)")
    ax.legend(loc="upper left", fontsize=8)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(args.out, dpi=120)
    print(f"\nSaved {args.out}")


if __name__ == "__main__":
    main()
