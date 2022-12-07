#!/bin/bash
source /home/tzhu38/miniconda3/etc/profile.d/conda.sh
conda activate nerfactor
echo "================== Training nerfactor pt 2"
echo "================== Joint optimization (training and validation)"

scene='hotdog_voxel'
gpus='0'
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
shape_outdir="$proj_root/output/train/${scene}_shape"                   # EDIT ME
# REPO_DIR="$repo_dir" "$repo_dir/nerfactor/trainvali_run.sh" "$gpus" --config='shape.ini' --config_override="data_root=$data_root,imh=$imh,near=$near,far=$far,use_nerf_alpha=$use_nerf_alpha,data_nerf_root=$surf_root,outroot=$shape_outdir,viewer_prefix=$viewer_prefix,overwrite=$overwrite"

# II. Joint Optimization (training and validation)
shape_ckpt="$shape_outdir/lr1e-2/checkpoints/ckpt-1"                    # EDIT ME
brdf_ckpt="$proj_root/output/train/merl_512/lr1e-2/checkpoints/ckpt-50" # EDIT ME
if [[ "$scene" == pinecone || "$scene" == vasedeck || "$scene" == scan* ]]; then
   # Real scenes: NeRF & DTU
   xyz_jitter_std=0.001
else
   xyz_jitter_std=0.01
fi
test_envmap_dir="$proj_root/data/envmaps/for-render_h16/test"
shape_mode='finetune'
outroot="$proj_root/output/train/${scene}_${model}_white_lights"
REPO_DIR="$repo_dir" "$repo_dir/nerfactor/trainvali_run.sh" "$gpus" --config="$model.ini" --config_override="data_root=$data_root,imh=$imh,near=$near,far=$far,use_nerf_alpha=$use_nerf_alpha,data_nerf_root=$surf_root,shape_model_ckpt=$shape_ckpt,brdf_model_ckpt=$brdf_ckpt,xyz_jitter_std=$xyz_jitter_std,test_envmap_dir=$test_envmap_dir,shape_mode=$shape_mode,outroot=$outroot,viewer_prefix=$viewer_prefix,overwrite=$overwrite"
