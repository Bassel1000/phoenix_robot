#!/bin/bash
# Script to initialize TF and AMCL Pose
echo "Starting static transform for Lidar..."
ros2 run tf2_ros static_transform_publisher --x 0 --y 0 --z 0.1 --yaw 0 --pitch 0 --roll 0 --frame-id base_link --child-frame-id lidar_link &

sleep 2

echo "Publishing initial pose to AMCL..."
ros2 topic pub --once /initialpose geometry_msgs/msg/PoseWithCovarianceStamped "{
  header: {
    stamp: 'now',
    frame_id: 'map'
  },
  pose: {
    pose: {
      position: {x: 0.0, y: 0.0, z: 0.0},
      orientation: {x: 0.0, y: 0.0, z: 0.0, w: 1.0}
    },
    covariance: [0.25, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.25, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.06853891945200942, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.06853891945200942, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.06853891945200942]
  }
}"
