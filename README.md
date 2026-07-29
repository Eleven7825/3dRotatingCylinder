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

> **Torch note:** compute nodes cannot access `/archive`.  Set `IBAMR_SCRATCH_DIR`
> to a path on `/scratch` so the SIF, executable, and run output land where the
> job can reach them.  Do this **once** per shell session (or add it to `~/.bashrc`):
>
> ```bash
> export IBAMR_SCRATCH_DIR=/scratch/$USER/3dRotatingCylinder
> ```
>
> Then deploy the built artifacts there the first time (or after a rebuild), from a login node:
>
> ```bash
> ./sync-archive-scratch.sh push
> ```

Runs are defined by **cases**. List them by running with no arguments:

```bash
module load anaconda3/2025.06   # needed for numpy (generate_vertex.py)

python3 setup_run.py
#   endcaps
#   faster_nofin

IBAMR_SCRATCH_DIR=/scratch/$USER/3dRotatingCylinder python3 setup_run.py faster_nofin
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
tail -f $IBAMR_SCRATCH_DIR/runs/faster_nofin_<stamp>/ibamr-rotating-cylinder-<jobid>.out
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

Open `viz_cylinder3d/` in [VisIt](https://visit-dav.github.io/visit-website/):

1. Go to [ood.torch.hpc.nyu.edu](https://ood.torch.hpc.nyu.edu) and request an interactive session (e.g. a Desktop app) with enough resources for VisIt.
2. Once the session opens, launch VisIt from a terminal in that session:
   ```
   /scratch/sc7825/software/visit/bin/visit
   ```
3. In the VisIt GUI, first add the source database: **File -> Open**, navigate to the run's *parent* directory (one level above `viz_cylinder3d`), and open `dumps.visit`.
4. To resume the session, go to **File -> Restore Session...**, browse to the run's `viz_cylinder3d` directory, and select the `.session` file to resume the session.

#### Test example

To try it with an existing run, restore this session file:

```
/scratch/sc7825/3dRotatingCylinder/runs/faster_3fin_2026-07-27_00-38-02/viz_cylinder3d/visit.compoents.session
```

Note: the session's database paths are relative to the run's *parent* directory (one level above `viz_cylinder3d`), so if VisIt reports it can't find `dumps.visit`, `cd` into `faster_3fin_2026-07-27_00-38-02` before launching `visit`, or set that as VisIt's working/browse directory before restoring the session.

---

## Syncing archive <-> scratch

`/scratch` is where jobs run and is **purged after 60 days of inactivity**; `/archive`
(this repo) is not. Since compute nodes can't reach `/archive`, use
`sync-archive-scratch.sh` from a **login node** to move data between the two:

```bash
./sync-archive-scratch.sh push   # archive -> scratch: deploy build/main3d + singularity/ibamr.sif before running jobs
./sync-archive-scratch.sh pull   # scratch -> archive: back up runs/ so results survive the purge
```

Add `--dry-run` to preview either direction before it copies anything. Run `pull`
periodically (e.g. after a batch of runs finishes) so completed results aren't
left exposed to the purge on `/scratch`.

---

## Interactive run (no SLURM)

For quick tests or debugging, run directly in the container on the login node:

```bash
module load anaconda3/2025.06
export IBAMR_SCRATCH_DIR=/scratch/$USER/3dRotatingCylinder
IBAMR_SCRATCH_DIR=$IBAMR_SCRATCH_DIR python3 setup_run.py faster_nofin --no-submit
cd $IBAMR_SCRATCH_DIR/runs/<case>_<stamp>
bash /archive/$USER/3dRotatingCylinder/singularity/run-IBAMR-torch.bash \
     mpirun -np 4 $IBAMR_SCRATCH_DIR/build/main3d input3d
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
