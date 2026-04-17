#!/bin/bash
echo "Launching RViz2 with Nav2 Default View..."
cd ~/ambers_ws || exit
source install/setup.bash
rviz2 -d $(ros2 pkg prefix nav2_bringup)/share/nav2_bringup/rviz/nav2_default_view.rviz