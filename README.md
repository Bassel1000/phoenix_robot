# Phoenix Robot

Intelligent Mobile Robot for autonomous flame location detection and suppression. This repository utilizes a split-node architecture, distributing tasks across a stationary vision node, a local simulation environment, and the physical edge hardware.

---

## 🚀 Quick Start (Using Helper Scripts)
To make running the simulation and mapping processes easier, this repository includes a dedicated `scripts/` directory. 

**First time setup (Make scripts executable):**
```bash
chmod +x scripts/*.sh
```

**Available Automation Scripts:**

- `./scripts/build_sim.sh` - Updates and builds the simulation packages.
- `./scripts/launch_gazebo.sh` - Launches the Gazebo simulation environment.
- `./scripts/launch_display.sh` - Launches the robot description display.
- `./scripts/run_teleop.sh` - Starts the teleop keyboard node to drive Phoenix manually.
- `./scripts/start_slam.sh` - Starts the SLAM Toolbox for environment mapping.
- `./scripts/save_map.sh` - Saves the generated SLAM map.
- `./scripts/launch_nav2.sh` - Launches the Nav2 Stack with the generated map.
- `./scripts/launch_rviz_nav2.sh` - Launches RViz2 with the Nav2 default view.
- `./scripts/start_pi_camera_stream.sh` - Starts the Raspberry Pi camera streaming for the vision node.

## 📡 MQTT Integration (Local Mosquitto)

We have migrated from Cloud MQTT (HiveMQ) to a **Local Mosquitto Broker** to improve latency and system reliability, removing the dependency on an active internet connection.

The `Local_MQTT/` directory contains:
- `vision_node.py` - Simulates the vision node publishing fire and human detection alerts via MQTT.
- `robot_integration.py` - The central robot logic that listens to MQTT topics (fire/human alerts) and monitors connection heartbeats to activate fail-safes (e.g., motor stop/pump activation).
- `robot_sub.py` - A simple debug node to verify message transmission.

**Prerequisites:** Ensure your local Mosquitto broker is running on `localhost:1883`.

## 💻 1. Vision Node Setup (Native Windows / Laptop)

This environment handles the object detection pipelines and visual tracking. It features a scalable structure for different cameras via the `CameraStream` class, supporting both the TP-Link Tapo C210 and Raspberry Pi cameras. Dedicated robust models are provided for **Fire Detection** and **Human Detection**.

**Prerequisites:** Python 3.8+

1. Navigate to the vision node directory:
   ```bash
   cd vision_node
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the primary vision architecture or testing script (e.g., `Vision.py` or the Tapo Pi testing scripts):
   ```bash
   python Vision.py
   ```

## 🖥️ 2. Simulation & Modeling Setup (WSL / Ubuntu)

This environment is used for testing the ROS 2 Navigation stack and SLAM using Gazebo Harmonic before deploying to physical hardware.

**Prerequisites:** ROS 2 (Jazzy/Humble) and Gazebo Harmonic.

1. Navigate to the workspace root:
   ```bash
   cd ambers_ws
   ```
2. Build only the simulation package (or use `./scripts/build_sim.sh`):
   ```bash
   colcon build --packages-select phoenix_description --symlink-install
   ```
3. Source the workspace:
   ```bash
   source install/setup.bash
   ```
4. Launch the simulation (or use `./scripts/launch_gazebo.sh`):
   ```bash
   ros2 launch phoenix_description gazebo.launch.py
   ```

## 🍓 3. Mobile Edge Node Setup (Raspberry Pi 5)

This environment runs natively on the robot, handling GPIO pins, UART LiDAR, I2C servos, and the BTS7960 motor drivers (with newly implemented smooth speed control and velocity interpolation).

**Prerequisites:** ROS 2 installed on the Pi, `gpiozero`, `paho-mqtt`, and `serial`.

1. Navigate to the workspace root on the Pi:
   ```bash
   cd ambers_ws
   ```
2. Build only the hardware control package:
   ```bash
   colcon build --packages-select phoenix_control --symlink-install
   ```
3. Source the workspace:
   ```bash
   source install/setup.bash
   ```
4. Launch the hardware nodes (Example):
   ```bash
   ros2 run phoenix_control motor_controller
   ```