#!/bin/bash
echo "Launching Nav2 Stack with new_warehouse_map..."
cd ~/ambers_ws || exit
source install/setup.bash
ros2 launch nav2_bringup bringup_launch.py use_sim_time:=True map:=$HOME/ambers_ws/src/phoenix_description/maps/new_warehouse_map.yaml