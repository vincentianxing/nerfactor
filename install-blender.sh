proj_root='/home/dhu24/GitHub/nerfactor-project'
repo_dir="$proj_root/nerfactor"
# Make directory
mkdir "$proj_root"/software
cd "$proj_root"/software
# Download
wget https://download.blender.org/release/Blender3.3/blender-3.3.1-linux-x64.tar.xz
# Unzip the pre-built binaries
tar -xvf blender-3.3.1-linux-x64.tar.xz
