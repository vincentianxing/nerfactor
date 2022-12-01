#!/bin/bash
source /home/tzhu38/miniconda3/etc/profile.d/conda.sh
conda activate nerfactor
echo "================== Training BRDF MLP"

gpus='0'

# I. Learning BRDF Priors (training and validation)
proj_root='/home/tzhu38'
repo_dir="$proj_root/nerfactor"
data_root="$proj_root/data/brdf_merl_npz/ims256_envmaph16_spp1"
outroot="$proj_root/output/train/merl_our_own"
viewer_prefix='http://vision38.csail.mit.edu' # or just use ''
REPO_DIR="$repo_dir" "$repo_dir/nerfactor/trainvali_run.sh" "$gpus" --config='brdf.ini' --config_override="data_root=$data_root,outroot=$outroot,viewer_prefix=$viewer_prefix"

# II. Exploring the Learned Space (validation and testing)
ckpt="$outroot/lr1e-2/checkpoints/ckpt-50"
REPO_DIR="$repo_dir" "$repo_dir/nerfactor/explore_brdf_space_run.sh" "$gpus" --ckpt="$ckpt"
