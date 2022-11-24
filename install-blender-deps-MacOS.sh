cd /Applications/Blender.app/Contents/Resources/3.3/python/bin
# Install pip for THIS Blender-bundled Python
curl https://bootstrap.pypa.io/get-pip.py | ./python3.10
# If the above fails, make sure you deactivate your Conda environment
# Use THIS pip to install other dependencies
./pip install absl-py tqdm ipython numpy Pillow opencv-python
