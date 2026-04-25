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
