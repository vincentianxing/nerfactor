cd ../software/blender-2.83.4-linux64/2.83/python/bin
# Install pip for THIS Blender-bundled Python
curl https://bootstrap.pypa.io/get-pip.py | ./python3.7m
# If the above fails, make sure you deactivate your Conda environment
# Use THIS pip to install other dependencies
./pip install absl-py tqdm ipython numpy Pillow opencv-python
