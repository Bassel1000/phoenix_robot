#!/bin/bash
echo "Building Phoenix..."
cd ~/ambers_ws
colcon build
source install/setup.bash
echo "Build complete!"