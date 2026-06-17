#!/bin/bash
echo "Building Phoenix Simulation..."
cd ~/ambers_ws
colcon build
source install/setup.bash
echo "Build complete!"