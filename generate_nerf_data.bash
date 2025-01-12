scene='hotdog'
light='2188'
proj_root='/Users/dylan/GitHub/nerfactor-project'
blender_bin="/opt/homebrew/bin/blender"
repo_dir="$proj_root/nerfactor"
scene_path="$proj_root/data/scenes/$scene.blend"
light_path="$proj_root/data/envmaps/for-render_h16/train/$light.hdr"
cam_dir="$proj_root/data/cams/nerf"
test_light_dir="$proj_root/data/envmaps/for-render_h16/test"
light_inten='3'
if [[ "$scene" == drums || "$scene" == lego ]]; then
    add_glossy_albedo='true'
else
    add_glossy_albedo='false'
fi
outdir="$proj_root/data/render_outdoor_inten${light_inten}_gi/${scene}_${light}"
REPO_DIR="$repo_dir" BLENDER_BIN="$blender_bin" 
"$repo_dir/data_gen/nerf_synth/render_run.sh" --scene_path="$scene_path" 
--light_path="$light_path" --cam_dir="$cam_dir" 
--test_light_dir="$test_light_dir" --light_inten="$light_inten" 
--add_glossy_albedo="$add_glossy_albedo" --outdir="$outdir" 1> /dev/null
# Note: We used stdout redirection to silence Blender's rendering prints
