proj_root='/home/dhu24/GitHub/nerfactor-project'
repo_dir="$proj_root/nerfactor"
# Make directory
mkdir "$proj_root"/software
cd "$proj_root"/software
# Download
wget https://download.blender.org/release/Blender2.83/blender-2.83.4-linux64.tar.xz
# Unzip the pre-built binaries
tar -xvf blender-2.83.4-linux64.tar.xz
