#!/bin/bash

echo "========================================"
echo " Building Phoenix Workspace (ambers_ws) "
echo "========================================"

# Navigate to the workspace directory
cd ~/ambers_ws || { echo "Failed to find ~/ambers_ws"; exit 1; }

# Build all packages using symlinks for Python and config files
# This saves you from having to rebuild every time you edit a python script!
colcon build --symlink-install

# Check if the build was successful
if [ $? -eq 0 ]; then
    echo "========================================"
    echo " Build successful! Sourcing workspace..."
    echo "========================================"
    
    # Source the newly built workspace
    source install/setup.bash
    
    echo "Ready to go!"
else
    echo "========================================"
    echo " Build FAILED. Check the errors above."
    echo "========================================"
fi