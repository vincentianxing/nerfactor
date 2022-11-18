#!/bin/bash
#? -cwd

source /home/tzhu38/miniconda3/etc/profile.d/conda.sh
echo "$SHELL"

# env

conda activate nerfactor

echo "Activated nerfactor environment"

/home/tzhu38/nerfactor/train_geom_from_nerf.sh
