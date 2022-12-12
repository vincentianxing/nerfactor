# /home/dhu24/miniconda3/condabin/conda init
# /home/dhu24/miniconda3/condabin/conda activate nerfactor

# scene='lego_3072'
# gpus='0'
# proj_root='/home/dhu24/GitHub'
# repo_dir="$proj_root/nerfactor"
# viewer_prefix='http://vision38.csail.mit.edu' # or just use ''
# data_root="$proj_root/james/data/$scene"

## Mandy Script below ### --------------------
#!/bin/bash                                                                     
#? -cwd                                                                         

# #scp -r /Users/mandyhe/Documents/Fall2022-2023/CSCI2951I\ /nerfactor/data/render_outdoor_inten3_gi/drums_new_black/ mhe26@ssh.cs.brown.edu:/home/mhe26/cs2951I/james/data/
#scp -r /Users/mandyhe/Documents/Fall2022-2023/CSCI2951I\ /nerfactor/data/render_outdoor_inten3_gi/hotdog_new_black/ mhe26@ssh.cs.brown.edu:/home/mhe26/cs2951I/james/data/
#scp -r /Users/mandyhe/Documents/Fall2022-2023/CSCI2951I\ /nerfactor/data/render_outdoor_inten3_gi/hotdog_voxel_bright_new_black/ mhe26@ssh.cs.brown.edu:/home/mhe26/cs2951I/james/data/
#scp -r /Users/mandyhe/Documents/Fall2022-2023/CSCI2951I\ /nerfactor/data/render_outdoor_inten3_gi/hotdog_voxel_even_black/ mhe26@ssh.cs.brown.edu:/home/mhe26/cs2951I/james/data/

source /home/mhe26/miniconda3/etc/profile.d/conda.sh
echo "$SHELL"    
                                                                     
conda activate nerfactor
echo "Activated nerfactor environment"

scene='hotdog_2163'
gpus='0,1,2,3,4,5,6,7'
proj_root='/home/mhe26/cs2951I'
repo_dir="$proj_root/nerfactor"
viewer_prefix='http://vision38.csail.mit.edu' # or just use ''                  
data_root="$proj_root/james/data/$scene"

if [[ "$scene" == scan* ]]; then
    # DTU scenes
    imh='256'
else
    imh='512'
fi
if [[ "$scene" == ficus* || "$scene" == hotdog_probe_16-00_latlongmap ]]; then
    lr='1e-4'
else
    lr='5e-4'
fi
trained_nerf="$proj_root/james/output/train/${scene}_nerf/lr$lr"
occu_thres='0.5'
if [[ "$scene" == pinecone* || "$scene" == scan* ]]; then
    # pinecone and DTU scenes
    scene_bbox='-0.3,0.3,-0.3,0.3,-0.3,0.3'
elif [[ "$scene" == vasedeck* ]]; then
    scene_bbox='-0.2,0.2,-0.4,0.4,-0.5,0.5'
else
    # We don't need to bound the synthetic scenes
    scene_bbox=''
fi
out_root="$proj_root/james/output/surf/$scene"
mlp_chunk='400000' # bump this up until GPU gets OOM for faster computation
REPO_DIR="$repo_dir" "$repo_dir/nerfactor/geometry_from_nerf_run.sh" "$gpus" --data_root="$data_root" --trained_nerf="$trained_nerf" --out_root="$out_root" --imh="$imh" --scene_bbox="$scene_bbox" --occu_thres="$occu_thres" --mlp_chunk="$mlp_chunk"