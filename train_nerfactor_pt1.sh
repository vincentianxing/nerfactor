#!/bin/bash
source /home/tzhu38/miniconda3/etc/profile.d/conda.sh
conda activate nerfactor
echo "================== Training nerfactor pt 1"
echo "================== Shape pre-training"

scene='hotdog_voxel'
gpus='0,1,2,3'
model='nerfactor'
overwrite='True'
proj_root='/home/tzhu38'
repo_dir="$proj_root/nerfactor"
viewer_prefix='http://vision38.csail.mit.edu' # or just use ''

# I. Shape Pre-Training
data_root="$proj_root/james/$scene"
if [[ "$scene" == scan* ]]; then
    # DTU scenes
    imh='256'
else
    imh='256'
fi
if [[ "$scene" == pinecone || "$scene" == vasedeck || "$scene" == scan* ]]; then
    # Real scenes: NeRF & DTU
    near='0.1'; far='2'
else
    near='2'; far='6'
fi
if [[ "$scene" == pinecone || "$scene" == vasedeck || "$scene" == scan* ]]; then
    # Real scenes: NeRF & DTU
    use_nerf_alpha='True'
else
    use_nerf_alpha='False'
fi

surf_root="$proj_root/output/surf/$scene"
shape_outdir="$proj_root/output/train/${scene}_shape"
REPO_DIR="$repo_dir" "$repo_dir/nerfactor/trainvali_run.sh" "$gpus" --config='shape.ini' --config_override="data_root=$data_root,imh=$imh,near=$near,far=$far,use_nerf_alpha=$use_nerf_alpha,data_nerf_root=$surf_root,outroot=$shape_outdir,viewer_prefix=$viewer_prefix,overwrite=$overwrite"
