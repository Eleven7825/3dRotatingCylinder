#!/usr/bin/env bash
# Sync 3dRotatingCylinder between /archive (this git repo; not reachable from
# compute nodes) and /scratch (where SLURM jobs actually read/write; purged
# after 60 days of inactivity).
#
# Usage:
#   ./sync-archive-scratch.sh push [rsync-extra-args...]   # archive -> scratch
#   ./sync-archive-scratch.sh pull [rsync-extra-args...]   # scratch -> archive
#
# push:  deploy the built container + binary to scratch before submitting jobs.
# pull:  back up run outputs from scratch to archive so they survive the purge.
#
# Extra args are passed through to rsync, e.g. --dry-run to preview.
#
# Must be run from a login node — compute nodes cannot reach /archive.

set -euo pipefail

ARCHIVE_DIR="/archive/$USER/3dRotatingCylinder"
SCRATCH_DIR="/scratch/$USER/3dRotatingCylinder"

mode="${1:-}"
[[ $# -gt 0 ]] && shift

usage() {
    echo "Usage: $0 {push|pull} [rsync-extra-args...]" >&2
    exit 1
}

[[ "$mode" == "push" || "$mode" == "pull" ]] || usage

RSYNC_OPTS=(-avh --progress "$@")

case "$mode" in
push)
    echo "== push: $ARCHIVE_DIR -> $SCRATCH_DIR (build artifacts + container) =="
    mkdir -p "$SCRATCH_DIR/build" "$SCRATCH_DIR/singularity"
    rsync "${RSYNC_OPTS[@]}" "$ARCHIVE_DIR/build/" "$SCRATCH_DIR/build/"
    rsync "${RSYNC_OPTS[@]}" --exclude '.claude' --exclude '*.out' --exclude '*.err' \
        "$ARCHIVE_DIR/singularity/" "$SCRATCH_DIR/singularity/"
    ;;
pull)
    echo "== pull: $SCRATCH_DIR -> $ARCHIVE_DIR (run outputs) =="
    mkdir -p "$ARCHIVE_DIR/runs"
    rsync "${RSYNC_OPTS[@]}" "$SCRATCH_DIR/runs/" "$ARCHIVE_DIR/runs/"
    ;;
esac
