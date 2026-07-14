#!/usr/bin/env python3
"""
setup_run.py — Prepare and submit an IBAMR rotating cylinder run for a case.

    python3 setup_run.py <case-name>              # e.g. faster_nofin
    python3 setup_run.py <case-name> --no-submit  # stage the run folder only

Cases live in cases/<case-name>/ (see cases/README.md). This script stages a
timestamped run folder:

    runs/<case-name>_YYYY-MM-DD_HH-MM-SS/
        archive/              snapshot of the sources + case files used
        input3d               copied from the case
        cylinder3d.vertex     copied from the case
        indices               copied from the case
        viz_cylinder3d/       pre-created output dirs
        restart_IB3d/
        cylinder_dump/
        Dump--Cylinder/

and submits it to SLURM. The vertex file is verified against the case's
geometry.json before submission, so a stale mesh cannot silently be run.
"""

import argparse
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
CASES_DIR = PROJECT_DIR / "cases"
RUNS_DIR = PROJECT_DIR / "runs"

# Source files snapshotted into archive/ so a run records exactly what produced it.
SOURCE_FILES = [
    "example.C",
    "CartGridBodyForce.C",
    "CartGridBodyForce.h",
    "ForceProjector.C",
    "ForceProjector.h",
    "OscillatingCylinderKinematics.h",
    "RotatingCylinderKinematics.C",
    "RotatingCylinderKinematics.h",
    "CMakeLists.txt",
    "Makefile",
    "setup_run.py",
    "tools/generate_vertex.py",
    "singularity/ibamr.def",
    "singularity/build-container.sh",
    "singularity/run-IBAMR-torch.bash",
    "singularity/run-simulation.slurm",
]

# Files copied from the case into the run folder — what the solver actually reads.
CASE_FILES = ["input3d", "cylinder3d.vertex", "indices"]

SIM_OUTPUT_DIRS = [
    "viz_cylinder3d",
    "restart_IB3d",
    "cylinder_dump",
    "Dump--Cylinder",
]


def list_cases():
    if not CASES_DIR.is_dir():
        return []
    return sorted(d.name for d in CASES_DIR.iterdir()
                  if d.is_dir() and (d / "input3d").exists())


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("case", nargs="?", help="case name under cases/")
    p.add_argument("--no-submit", action="store_true",
                   help="stage the run folder but do not call sbatch")
    args = p.parse_args()

    cases = list_cases()
    if not args.case:
        print("Usage: python3 setup_run.py <case-name>\n\nAvailable cases:")
        for c in cases:
            print(f"  {c}")
        sys.exit(1)

    case_dir = CASES_DIR / args.case
    if not case_dir.is_dir():
        print(f"ERROR: no such case: {args.case}\n\nAvailable cases:")
        for c in cases:
            print(f"  {c}")
        sys.exit(1)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_dir = RUNS_DIR / f"{args.case}_{timestamp}"

    print(f"=== Setting up run: {args.case} ===")
    print(f"  Case directory: {case_dir}")
    print(f"  Run directory : {run_dir}\n")

    # --- 1. Verify the case's mesh matches its geometry.json ------------------
    print("  [1/4] Verifying cylinder3d.vertex against geometry.json ...")
    check = subprocess.run(
        [sys.executable, str(PROJECT_DIR / "tools" / "generate_vertex.py"),
         str(case_dir), "--check"],
        capture_output=True, text=True,
    )
    if check.returncode != 0:
        print(check.stdout + check.stderr)
        print("  ERROR: the case's vertex file does not match its geometry.json.")
        print(f"         Regenerate it: python3 tools/generate_vertex.py {case_dir}")
        sys.exit(1)
    print("        vertex file matches geometry.json")

    # --- 2. Create the run folder --------------------------------------------
    run_dir.mkdir(parents=True)
    archive_dir = run_dir / "archive"
    archive_dir.mkdir()
    for d in SIM_OUTPUT_DIRS:
        (run_dir / d).mkdir()
    print("  [2/4] Created run directory structure")

    # --- 3. Copy case files + archive sources --------------------------------
    for name in CASE_FILES:
        src = case_dir / name
        if not src.exists():
            print(f"  ERROR: case file missing: {src}")
            sys.exit(1)
        shutil.copy2(src, run_dir / name)

    missing = []
    for rel in SOURCE_FILES:
        src = PROJECT_DIR / rel
        if src.exists():
            shutil.copy2(src, archive_dir / src.name)
        else:
            missing.append(rel)
    # The case definition is part of the provenance too.
    shutil.copy2(case_dir / "input3d", archive_dir / "input3d")
    shutil.copy2(case_dir / "geometry.json", archive_dir / "geometry.json")

    if missing:
        print(f"        WARNING: missing source files (not archived): {missing}")
    print(f"  [3/4] Copied {len(CASE_FILES)} case files, archived "
          f"{len(SOURCE_FILES) - len(missing)} sources → archive/")

    # --- 4. Submit -----------------------------------------------------------
    slurm_script = PROJECT_DIR / "singularity" / "run-simulation.slurm"
    executable = PROJECT_DIR / "build" / "main3d"
    sif = PROJECT_DIR / "singularity" / "ibamr.sif"

    if args.no_submit:
        print("\n  [4/4] --no-submit: run folder staged, not submitted.")
        print(f"\n=== Staged ===\n  Run folder : {run_dir}\n")
        return

    print("\n  [4/4] Submitting SLURM job ...")
    for label, path in [("executable", executable), ("container", sif),
                        ("slurm script", slurm_script)]:
        if not path.exists():
            print(f"  ERROR: {label} not found: {path}")
            if label == "executable":
                print("         Build first: bash singularity/run-IBAMR-torch.bash make-sim")
            sys.exit(1)

    result = subprocess.run(
        [
            "sbatch",
            f"--chdir={run_dir}",
            f"--export=ALL,IBAMR_PROJECT_DIR={PROJECT_DIR},IBAMR_SIF={sif},"
            f"IBAMR_EXECUTABLE={executable}",
            str(slurm_script),
            "input3d",
        ],
        cwd=str(run_dir), capture_output=True, text=True,
    )
    if result.returncode != 0:
        print("  ERROR: sbatch failed:\n")
        print(result.stderr)
        sys.exit(1)

    job_info = result.stdout.strip()
    job_id = job_info.split()[-1] if job_info else "?"
    print(f"        {job_info}")
    print(f"""
=== Run submitted ===
  Case       : {args.case}
  Run folder : {run_dir}
  Job ID     : {job_id}

  Monitor    : squeue -u $USER
  Output log : {run_dir}/ibamr-rotating-cylinder-{job_id}.out
  Cancel     : scancel {job_id}
""")


if __name__ == "__main__":
    main()
