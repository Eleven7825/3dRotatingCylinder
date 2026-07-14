# 3D Rotating Cylinder — IBAMR Simulation

Immersed boundary simulation of a 3D rotating cylinder (rotobot) in viscous flow, built with [IBAMR](https://ibamr.github.io/).

---

## Prerequisites

- NYU **Torch** HPC cluster (or any system with Apptainer ≥ 1.2 and SLURM)
- Git, Python 3 with numpy — load via `module load anaconda3/2025.06` on Torch
- No local IBAMR installation needed — everything runs inside a container

---

## Quick Start (first time)

### 1 — Clone the repo

```bash
git clone https://github.com/Eleven7825/3dRotatingCylinder.git
cd 3dRotatingCylinder
```

### 2 — Build the Singularity container

This step compiles IBAMR and all dependencies inside a container. It runs **once** and takes 1–3 hours.

```bash
module load apptainer

sbatch --job-name=build-ibamr \
       --time=4:00:00 --mem=32G --cpus-per-task=8 \
       --output=build-%j.log \
       --wrap="bash singularity/build-container.sh"
```

Wait for the job to finish:

```bash
squeue -u $USER          # shows running jobs
cat build-<jobid>.log    # check progress / errors
```

The container is written to `singularity/ibamr.sif`.

### 3 — Compile the simulation

```bash
bash singularity/run-IBAMR-torch.bash make-sim
```

Runs `cmake` + `make` inside the container. Binary lands at `build/main3d`.

### 4 — Set up and submit a run

Runs are defined by **cases**. List them by running with no arguments:

```bash
module load anaconda3/2025.06   # needed for numpy (generate_vertex.py)

python3 setup_run.py
#   endcaps
#   faster_nofin

python3 setup_run.py faster_nofin
```

The script:
1. Verifies the case's `cylinder3d.vertex` still matches its `geometry.json`
2. Creates a timestamped run folder, `runs/<case>_YYYY-MM-DD_HH-MM-SS/`
3. Copies the case's `input3d`, `cylinder3d.vertex` and `indices` into it
4. Archives the sources + case definition into `archive/` for provenance
5. Submits the SLURM job

Use `--no-submit` to stage the run folder without submitting.

Monitor the job:

```bash
squeue -u $USER
tail -f runs/faster_nofin_2026-07-14_11-48-15/ibamr-rotating-cylinder-<jobid>.out
```

Cancel if needed:

```bash
scancel <jobid>
```

### 5 — Visualize results

Output appears inside the run folder:

| Directory | Contents |
|-----------|----------|
| `viz_cylinder3d/` | VisIt/Silo visualization data |
| `cylinder_dump/` | Drag / force time series |
| `Dump--Cylinder/` | Constraint IB output |

Open `viz_cylinder3d/` in [VisIt](https://visit-dav.github.io/visit-website/).

---

## Interactive run (no SLURM)

For quick tests or debugging, run directly in the container on the login node:

```bash
module load anaconda3/2025.06
python3 setup_run.py faster_nofin --no-submit   # stage runs/<case>_<stamp>/
cd runs/<case>_<stamp>
bash ../../singularity/run-IBAMR-torch.bash mpirun -np 4 ../../build/main3d input3d
```

Drop into an interactive shell inside the container:

```bash
bash singularity/run-IBAMR-torch.bash
```

---

## Restarting a simulation

> **Note:** restart functionality has not been tested yet.

Pass the restart directory and step number as extra arguments:

```bash
sbatch --chdir=<run-folder> \
       --export=ALL,IBAMR_PROJECT_DIR=$(pwd),IBAMR_SIF=singularity/ibamr.sif,IBAMR_EXECUTABLE=build/main3d \
       singularity/run-simulation.slurm input3d restart_IB3d <step>
```

---

## Layout

```
cases/                    one directory per simulation case — see cases/README.md
  faster_nofin/           input3d + geometry.json + cylinder3d.vertex + indices
  endcaps/
tools/
  generate_vertex.py      builds a case's point cloud from its geometry.json
runs/                     staged/submitted runs (gitignored)
*.C, *.h                  solver sources — built by CMakeLists.txt / Makefile
singularity/              container definition and cluster scripts
setup_run.py              stage a case into runs/ and submit to SLURM
```

A **case** is a matched pair: `input3d` (flow/solver parameters) and
`geometry.json` (body parameters). `cylinder3d.vertex` and `indices` are
*generated* from `geometry.json` and must never be hand-edited — regenerate with

```bash
python3 tools/generate_vertex.py cases/<case-name>
```

`setup_run.py` re-verifies this before every submission, so a vertex file can't
silently drift out of sync with the geometry it claims to come from.

| File | Purpose |
|------|---------|
| `example.C` | Main simulation driver |
| `cases/<case>/input3d` | Flow/solver parameters (grid, timestep, viscosity, BCs) |
| `cases/<case>/geometry.json` | Body parameters (radius, length, end caps, fins) |
| `cases/<case>/cylinder3d.vertex` | IB point cloud (generated; stored in git LFS) |
| `cases/<case>/indices` | End-cap / fin point markers (generated) |
| `tools/generate_vertex.py` | Generate a case's vertex + indices from `geometry.json` |
| `CMakeLists.txt` | CMake build definition |
| `singularity/ibamr.def` | Container definition (Ubuntu 22.04 + autoibamr) |
| `singularity/build-container.sh` | Build the `.sif` container image |
| `singularity/run-IBAMR-torch.bash` | Run any command inside the container |
| `singularity/run-simulation.slurm` | SLURM job script |
| `setup_run.py` | Stage a case into `runs/` and submit to SLURM |

Vertex files are ~95 MB each and are tracked with **git LFS** (`*.vertex`).
Make sure `git lfs install` has been run before cloning or pushing.
