#!/bin/bash
echo "Launching Gazebo Simulation..."
cd ~/ambers_ws
source install/setup.bash
ros2 launch phoenix_description gazebo.launch.py