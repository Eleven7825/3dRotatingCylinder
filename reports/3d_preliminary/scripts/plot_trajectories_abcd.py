#!/usr/bin/env python3
"""Regenerate figures/trajectories_abcd.png: center-of-mass trajectories
for exactly the 4 cases shown as panels (a)-(d) of the domain schematic:
  a = faster_nofin_full_span  (periodic z, no fins)
  b = faster_nofin_large      (wall z, no fins)
  c = faster_midfin           (periodic z, one fin)
  d = faster_2fin             (periodic z, two fins)

Adapted from tools/plot_trajectories.py (same stitching/selection logic),
pointed at the real scratch run directory (run output isn't part of this
git repo) instead of IBAMR_SCRATCH_DIR.

    module load anaconda3/2025.06
    python3 reports/3d_preliminary/scripts/plot_trajectories_abcd.py
"""
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RUNS_DIR = Path("/scratch/sc7825/3dRotatingCylinder/runs")
OUT_DIR = Path(__file__).resolve().parent.parent / "figures"

DOMAIN_BOX = {"x": (-30, 120), "y": (-120, 30)}

CASES = {
    "faster_nofin_full_span": "(a) periodic $z$, no fins",
    "faster_nofin_large": "(b) wall $z$, no fins",
    "faster_midfin": "(c) periodic $z$, one fin",
    "faster_2fin": "(d) periodic $z$, two fins",
}

TIME_RE = re.compile(r"^Simulation time is\s+([-\d.eE+]+)")
COM_RE = re.compile(r"^center_of_mass:\s+([-\d.eE+]+)\s+([-\d.eE+]+)")


def case_run_dirs(case):
    pattern = re.compile(rf"^{re.escape(case)}_\d{{4}}-\d{{2}}-\d{{2}}_\d{{2}}-\d{{2}}-\d{{2}}$")
    return sorted((d for d in RUNS_DIR.iterdir() if d.is_dir() and pattern.match(d.name)),
                  key=lambda d: d.name)


def extract_trajectory(path, stride=20):
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


def folder_trajectory(run_dir, stride=20):
    """Stitch every job .out file in a run folder into one continuous
    trajectory, ordered by mtime (submission order). Where a later file's
    data overlaps the end of an earlier one (a restart resumes from a
    checkpoint that predates the earlier job's last logged point), the
    earlier file's overlapping tail is dropped in favor of the restart."""
    out_files = sorted(
        (f for f in run_dir.glob("ibamr-rotating-cylinder-*.out") if f.stat().st_size > 0),
        key=lambda f: f.stat().st_mtime,
    )
    ts, xs, ys = [], [], []
    for out_file in out_files:
        nts, nxs, nys = extract_trajectory(out_file, stride=stride)
        if not nts:
            continue
        if ts:
            cutoff = nts[0]
            while ts and ts[-1] >= cutoff:
                ts.pop(); xs.pop(); ys.pop()
        ts.extend(nts); xs.extend(nxs); ys.extend(nys)
    return (ts, xs, ys) if ts else None


def best_trajectory_for_case(case, stride=20):
    """Best (furthest-reaching) stitched trajectory across all of a case's
    run folders: a fresh restart only replaces an older one if it actually
    got further."""
    best_dir, best_traj = None, None
    for run_dir in case_run_dirs(case):
        traj = folder_trajectory(run_dir, stride=stride)
        if traj is None:
            continue
        if best_traj is None or traj[0][-1] > best_traj[0][-1]:
            best_dir, best_traj = run_dir, traj
    return best_dir, best_traj


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data = {}
    for case, label in CASES.items():
        run_dir, traj = best_trajectory_for_case(case)
        if traj is None:
            print(f"{case}: no run output found, skipping")
            continue
        ts, xs, ys = traj
        data[case] = traj
        print(f"{case}: {run_dir.name} -- {len(ts)} pts, t_end={ts[-1]:.4g}, "
              f"final=({xs[-1]:.4g},{ys[-1]:.4g})")

    fig, ax = plt.subplots(figsize=(8, 8))
    colors = {"faster_nofin_full_span": "tab:blue", "faster_nofin_large": "tab:orange",
              "faster_midfin": "tab:green", "faster_2fin": "tab:red"}
    for case, (ts, xs, ys) in data.items():
        c = colors[case]
        ax.plot(xs, ys, "-", color=c, label=CASES[case], linewidth=1.8, alpha=0.9)
        ax.plot(xs[0], ys[0], "o", color=c, markersize=6)
        ax.plot(xs[-1], ys[-1], "s", color=c, markersize=7)

    dx, dy = DOMAIN_BOX["x"], DOMAIN_BOX["y"]
    ax.plot([dx[0], dx[1], dx[1], dx[0], dx[0]],
            [dy[0], dy[0], dy[1], dy[1], dy[0]],
            "r--", linewidth=1.5, label="computational domain")

    ax.set_xlabel("$x$")
    ax.set_ylabel("$y$")
    ax.set_title("Center-of-mass trajectories (circle=start, square=end/last-logged)")
    ax.legend(loc="upper left", fontsize=9)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(alpha=0.3)

    fig.tight_layout()
    out_path = OUT_DIR / "trajectories_abcd.png"
    fig.savefig(out_path, dpi=200)
    print("\nSaved", out_path)


if __name__ == "__main__":
    main()
