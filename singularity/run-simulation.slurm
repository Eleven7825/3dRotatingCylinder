#!/bin/bash
#SBATCH --job-name=ibamr-rotating-cylinder
#SBATCH --account=torch_pr_767_general
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=128
#SBATCH --cpus-per-task=1
#SBATCH --mem=128G
#SBATCH --time=72:00:00
#SBATCH --output=%x-%j.out
#SBATCH --error=%x-%j.err

# -------------------------------------------------------------------------
# Usage (from the project root):
#   sbatch singularity/run-simulation.slurm
#   sbatch singularity/run-simulation.slurm input3d
#   sbatch singularity/run-simulation.slurm input3d restart_IB3d 5
#
# Outputs land in the project root:
#   viz_cylinder3d/     VisIt/Silo visualization
#   cylinder_dump/      drag/force output
#   Dump--Cylinder/     constraint IB output
#   IB3d_cylinder3d.log
# -------------------------------------------------------------------------

set -euo pipefail

# Copy SLURM output/error files into the run folder when the job ends (success or failure)
RUN_DIR="${PWD}"
copy_slurm_logs() {
    local out="${SLURM_SUBMIT_DIR}/${SLURM_JOB_NAME}-${SLURM_JOB_ID}.out"
    local err="${SLURM_SUBMIT_DIR}/${SLURM_JOB_NAME}-${SLURM_JOB_ID}.err"
    # Give SLURM a moment to finish flushing the file, then copy
    sleep 2
    [[ -f "${out}" ]] && cp "${out}" "${RUN_DIR}/" && echo "Copied ${out##*/} → run folder"
    [[ -f "${err}" ]] && cp "${err}" "${RUN_DIR}/" && echo "Copied ${err##*/} → run folder"
}
trap copy_slurm_logs EXIT

# Paths are passed as env vars by setup_run.py via --export.
# IBAMR_PROJECT_DIR, IBAMR_SIF, IBAMR_EXECUTABLE must be set.
if [[ -z "${IBAMR_PROJECT_DIR:-}" ]]; then
    echo "ERROR: IBAMR_PROJECT_DIR not set. Submit via setup_run.py."
    exit 1
fi
PROJECT_DIR="${IBAMR_PROJECT_DIR}"
SIF="${IBAMR_SIF}"
EXECUTABLE="${IBAMR_EXECUTABLE}"

INPUT_FILE="${1:-input3d}"
RESTART_ARGS="${@:2}"   # optional: <restart_dir> <restart_num>

echo "=== IBAMR Rotating Cylinder Simulation ==="
echo "  Job ID:      ${SLURM_JOB_ID}"
echo "  Node:        ${SLURMD_NODENAME}"
echo "  MPI tasks:   ${SLURM_NTASKS}"
echo "  Working dir: ${PROJECT_DIR}"
echo "  Input file:  ${INPUT_FILE}"
echo "  Container:   ${SIF}"
echo ""

# Working directory is set by --chdir in sbatch (run folder created by setup_run.py)
# Fall back to PROJECT_DIR if run directly without the wrapper
[[ "${PWD}" == "${PROJECT_DIR}" ]] || true   # no-op; cwd is already correct

srun apptainer exec \
    --bind "${PROJECT_DIR}":"${PROJECT_DIR}" \
    "${SIF}" \
    "${EXECUTABLE}" "${INPUT_FILE}" ${RESTART_ARGS}
