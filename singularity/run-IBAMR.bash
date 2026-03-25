#!/bin/bash

# https://stackoverflow.com/questions/1668649/how-to-keep-quotes-in-bash-arguments
args=''
for i in "$@"; do
  i="${i//\\/\\\\}"
  args="$args \"${i//\"/\\\"}\""
done

if [ "$args" == "" ]; then args="/bin/bash"; fi

module purge

export PATH=/share/apps/singularity/bin:$PATH

source /scratch/work/public/singularity/greene-ib-slurm-bind.sh

singularity exec \
  --bind /share/apps \
  --overlay /scratch/work/public/singularity/IBAMR-20210129-centos-8.2.2004.sqf:ro \
  /scratch/work/public/apps/greene/centos-8.2.2004.sif \
  /bin/bash -c "
if [ -e /ext3/env.sh ]; then source /ext3/env.sh; fi
module load ucx/intel/1.10.1
eval $args
"

# https://ibamr.github.io/linux
