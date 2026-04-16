#!/bin/bash
echo "Launching Display..."
cd ~/ambers_ws
source install/setup.bash
ros2 launch phoenix_description display.launch.py