#!/bin/bash

echo "$SHELL"
source /home/tzhu38/miniconda3/etc/profile.d/conda.sh
conda activate nerfactor

proj_root='/home/tzhu38'
repo_dir="$proj_root/nerfactor"
indir="$proj_root/data/brdf_merl"
ims='256'
outdir="$proj_root/data/brdf_merl_generated_data/ims${ims}_envmaph16_spp1"
REPO_DIR="$repo_dir" "$repo_dir"/data_gen/merl/make_dataset_run.sh "$indir" "$ims" "$outdir"
