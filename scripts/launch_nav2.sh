#!/bin/bash
echo "Launching Nav2 Stack with local_home map on physical hardware..."
cd ~/ambers_ws || exit
source install/setup.bash
ros2 launch nav2_bringup bringup_launch.py \
    use_sim_time:=False \
    map:=$HOME/ambers_ws/src/phoenix_description/maps/local_home.yaml \
    params_file:=$HOME/ambers_ws/src/phoenix_description/config/nav2_params.yaml