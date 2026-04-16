#!/bin/bash
echo "Building Phoenix Simulation..."
cd ~/ambers_ws
colcon build --packages-select phoenix_description
source install/setup.bash
echo "Build complete!"