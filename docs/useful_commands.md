# Useful Commands

## Check Raspberry Pi Camera
To verify that the Raspberry Pi camera is connected and recognized:
```bash
rpicam-hello --list-cameras
```

## Check Lidar
To verify that the Lidar is working correctly and publishing data:

View the raw scan data:
```bash
ros2 topic echo /scan
```

Check the publishing rate (frequency) of the Lidar:
```bash
ros2 topic hz /scan
```

## Build Packages
To build specific ROS 2 packages in this workspace:

Build `phoenix_control`:
```bash
cd ambers_ws
colcon build --packages-select phoenix_control
source install/setup.bash
```

Build `phoenix_description`:
```bash
cd ambers_ws
colcon build --packages-select phoenix_description
source install/setup.bash
```

Build both at the same time (with symlink install for development):
```bash
cd ambers_ws
colcon build --packages-select phoenix_control phoenix_description --symlink-install
source install/setup.bash
```

## Simulation Commands (Gazebo Harmonic)

Launch the full simulation stack (Gazebo, SLAM, Nav2, bridges, MQTT clients):
```bash
source /opt/ros/jazzy/setup.bash
cd ambers_ws
source install/setup.bash
ros2 launch phoenix_description simulation.launch.py
```

Check simulation sensor topic rates:
```bash
ros2 topic hz /scan
ros2 topic hz /odom
ros2 topic hz /camera/image_raw
```

Verify complete TF chain (`map -> odom -> base_footprint -> lidar_link`):
```bash
ros2 run tf2_tools view_frames
# Generates frames.pdf showing the live transform tree
```

Send manual velocity command to robot in Gazebo:
```bash
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.3}, angular: {z: 0.0}}"
```

## Fast Navigation Benchmark
Run the automated Nav2 navigation and velocity benchmark test:
```bash
python3 scripts/test_fast_navigation.py
```

## MQTT Diagnostics (Simulation & Hardware)

Listen to all robot status and telemetry:
```bash
mosquitto_sub -h localhost -p 1883 -t "phoenix/#" -v
```

Send manual drive commands via MQTT:
```bash
# Drive Forward
mosquitto_pub -h localhost -p 1883 -t "phoenix/cmd/move" -m "FORWARD"
# Stop
mosquitto_pub -h localhost -p 1883 -t "phoenix/cmd/move" -m "STOP"
```

Trigger suppression pump via MQTT:
```bash
mosquitto_pub -h localhost -p 1883 -t "phoenix/cmd/water" -m "ON"
mosquitto_pub -h localhost -p 1883 -t "phoenix/cmd/water" -m "OFF"
```

Dispatch autonomous navigation target directly to fire standoff location:
```bash
mosquitto_pub -h localhost -p 1883 -t "ambers/robot/navigation/target" -m '{"x": 2.2, "y": 1.8, "frame_id": "map"}'
```

## RViz2 3D Visualization & Goal Tools

Launch RViz2 with the Phoenix cybernetic profile:
```bash
source /opt/ros/jazzy/setup.bash
cd ambers_ws
source install/setup.bash
ros2 run rviz2 rviz2 -d $(ros2 pkg prefix phoenix_description)/share/phoenix_description/config/phoenix_sim.rviz
```
* Or launch simulation with RViz enabled automatically:
```bash
ros2 launch phoenix_description simulation.launch.py rviz:=true
```

## Simulation Process Hygiene (Clearing Background Instances)
To ensure no orphaned headless Gazebo or ROS processes accumulate in WSL2:
```bash
killall -9 gz-sim-server gz ruby 2>/dev/null
ros2 daemon stop && ros2 daemon start
```
