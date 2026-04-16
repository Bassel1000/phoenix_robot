#!/bin/bash
echo "Starting SLAM Toolbox..."
ros2 launch slam_toolbox online_async_launch.py params_file:=/opt/ros/jazzy/share/slam_toolbox/config/mapper_params_online_async.yaml use_sim_time:=true