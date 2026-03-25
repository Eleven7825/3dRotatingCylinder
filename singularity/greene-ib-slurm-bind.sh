#!/bin/bash

unset SINGULARITY_BIND

# file systems
export SINGULARITY_BINDPATH=/mnt,/scratch,/vast,/state/partition1

# IB related drivers and libraries
export SINGULARITY_BINDPATH=$SINGULARITY_BINDPATH,/etc/libibverbs.d,/usr/lib64/libibverbs,/usr/include/infiniband,/lib64/libibverbs,/usr/include/rdma,/usr/bin/ofed_info

#export SINGULARITY_BINDPATH=$SINGULARITY_BINDPATH,$(echo /usr/bin/ib*_* /usr/sbin/ib* /usr/lib64/libpmi* /lib64/libmlx*.so* /lib64/libib*.so* /lib64/libnl* /lib64/libosmcomp.so* /lib64/librdmacm*.so* | sed -e 's/ /,/g')

export SINGULARITY_BINDPATH=$SINGULARITY_BINDPATH,$(echo /usr/bin/ib*_* /usr/sbin/ib* /lib64/libmlx*.so* /lib64/libib*.so* /lib64/libnl* /lib64/librdmacm*.so* /usr/lib64/libuc* | sed -e 's/ /,/g')

# SLURM related
export SINGULARITY_BINDPATH=$SINGULARITY_BINDPATH,/opt/slurm,/usr/lib64/libmunge.so.2.0.0,/usr/lib64/libmunge.so.2,/var/run/munge
export SINGULARITYENV_PREPEND_PATH=/opt/slurm/bin

export SINGULARITY_BINDPATH=$SINGULARITY_BINDPATH,/etc/passwd 

if [[ -d /opt/slurm/lib64 ]]; then
    export SINGULARITY_CONTAINLIBS=$(echo /opt/slurm/lib64/libpmi* | xargs | sed -e 's/ /,/g')
fi
