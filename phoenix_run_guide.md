# Phoenix Robot - Execution & Mission Guide

This guide details how to boot up, connect, and run the Phoenix Fire-Fighting Robot in autonomous dynamic mapping mode.

---

## 🔌 Hardware Prerequisites & Wiring
Ensure the Okdo (LD06) LiDAR is connected to the Raspberry Pi 4 GPIO pins exactly as follows:

| LiDAR Wire | Description | Connection on Raspberry Pi |
| :--- | :--- | :--- |
| **VCC** (Blue) | 5V Power | Physical Pin 4 (5V) |
| **GND** (Red) | Ground | Physical Pin 6 (GND) |
| **TX** (Yellow) | Data Output | Physical Pin 12 (GPIO 18 / RX) |
| **PWM** (White) | Motor Speed | Physical Pin 10 (GPIO 15 / TX) |

---

## 🌐 Network Setup
1. Both your **Laptop** and the **Raspberry Pi** must be connected to the **same Wi-Fi network**.
2. Find the Raspberry Pi's IP address:
   ```bash
   hostname -I
   ```
3. Open `.env` or `vision_node/Vision.py` on your **Laptop** and configure the MQTT broker address:
   ```python
   # In .env:
   MQTT_BROKER=192.168.1.XX
   ```

---

## 🎮 Simulation Testing (Full Mission Without Hardware)

You can run and verify the entire autonomous loop on a PC or WSL2 without the physical robot using Gazebo Harmonic, Nav2, SLAM Toolbox, and the Web Command Center.

### Step 1: Start Mosquitto Broker with WebSockets
In a terminal, start Mosquitto supporting WebSockets on port 9001:
```bash
# In Linux / WSL2:
sudo systemctl start mosquitto
# Or run with the custom config:
mosquitto -c /etc/mosquitto/conf.d/websocket.conf -v
```

### Step 2: Launch Gazebo Harmonic Simulation & Full ROS Stack
In WSL2 or Linux terminal:
```bash
source /opt/ros/jazzy/setup.bash
cd /mnt/d/Phoenix/ambers_ws
source install/setup.bash
ros2 launch phoenix_description simulation.launch.py
```
* **What this runs:**
  - Gazebo Harmonic with `phoenix_test_world.sdf` and an emissive fire target cylinder at `(2.5, 2.0, 0.2)`.
  - Spawns the Phoenix robot model with Deep Crimson livery and Sky-Blue wheels.
  - Bridges clock, scan, cmd_vel, odom, and camera image between Gazebo and ROS 2.
  - Launches `simulation_odom_tf` dynamic odometry broadcaster.
  - Launches SLAM Toolbox asynchronous mapping.
  - Automatically delays Nav2 by 20s until TF `map -> odom -> base_footprint` is stable.
  - Launches `mqtt_nav_client`, `mqtt_motor_bridge`, `pump_controller`, and `nozzle_controller` with `use_sim_time:=True`.

### Step 3: Connect Web Command Center
1. Open `Phoenix_Web_Command_Center/index.html` in your browser.
2. In the **⚙ Settings** tab, click the **"Local Sim (9001)"** target preset button (sets broker to `ws://localhost:9001/mqtt`).
3. Click **⚡ CONNECT TO BROKER**. The topbar indicator will turn green (`SYSTEM ACTIVE`, `MQTT ONLINE`).
4. Toggle the mode switch to **MANUAL** to drive the robot with the D-Pad, test water spray, or move the nozzle in Gazebo!

### Step 4: Dispatch Autonomous Navigation Goal
- **Option A (Via Web HUD):** In the **MANUAL** / Navigation panel, enter target coordinates (e.g. `X: 2.0`, `Y: 1.5`) and click **SEND**.
- **Option B (Via CLI Action):**
  ```bash
  ros2 action send_goal /navigate_to_pose nav2_msgs/action/NavigateToPose \
    "{pose: {header: {frame_id: map}, pose: {position: {x: 2.0, y: 1.5}, orientation: {w: 1.0}}}}"
  ```
- **Option C (Via MQTT Target Topic):**
  ```bash
  mosquitto_pub -h localhost -p 1883 -t "ambers/robot/navigation/target" -m '{"x": 2.0, "y": 1.5, "frame_id": "map"}'
  ```

---

## 🚀 Physical Robot Run Order (Raspberry Pi 4)

Once physical hardware is connected, launch all robot nodes (lidar, navigation, SLAM, motor controllers, camera, etc.) simultaneously using the unified bringup launch file. Open **1 terminal** on the Raspberry Pi (via SSH) and run:

```bash
export ROS_DOMAIN_ID=30
source ~/ambers_ws/install/setup.bash
ros2 launch phoenix_description phoenix_bringup.launch.py
```

<details>
<summary><b>🛠️ Manual Debugging Mode (10 Terminals)</b></summary>

If you need to debug specific nodes, you can still run them in separate terminal windows:

### Terminal 1: Lidar Publisher (Driver)
```bash
export ROS_DOMAIN_ID=30
source ~/ambers_ws/install/setup.bash
ros2 run phoenix_control lidar_publisher
```

### Terminal 2: Laser Odometry & Transforms
```bash
export ROS_DOMAIN_ID=30
source ~/ambers_ws/install/setup.bash
ros2 launch phoenix_description laser_odom.launch.py
```

### Terminal 3: SLAM Toolbox (Dynamic Mapping)
```bash
export ROS_DOMAIN_ID=30
source ~/ambers_ws/install/setup.bash
ros2 launch slam_toolbox online_async_launch.py slam_params_file:=/home/ambers/ambers_ws/src/phoenix_description/config/mapper_params_online_async.yaml use_sim_time:=False
```

### Terminal 4: Nav2 Stack
```bash
export ROS_DOMAIN_ID=30
source ~/ambers_ws/install/setup.bash
ros2 launch nav2_bringup navigation_launch.py use_sim_time:=False params_file:=/home/ambers/ambers_ws/src/phoenix_description/config/nav2_params.yaml
```

### Terminal 5: Motor Controller
```bash
export ROS_DOMAIN_ID=30
source ~/ambers_ws/install/setup.bash
ros2 run phoenix_control motor_controller
```

### Terminal 6: MQTT Navigation Client
```bash
export ROS_DOMAIN_ID=30
source ~/ambers_ws/install/setup.bash
ros2 run phoenix_control mqtt_nav_client
```

### Terminal 7: Pump Controller
```bash
export ROS_DOMAIN_ID=30
source ~/ambers_ws/install/setup.bash
ros2 run phoenix_control pump_controller
```

### Terminal 8: Nozzle Controller
```bash
export ROS_DOMAIN_ID=30
source ~/ambers_ws/install/setup.bash
ros2 run phoenix_control nozzle_controller
```

### Terminal 9: Pi Camera Stream
```bash
cd ~/ambers_ws
bash ~/ambers_ws/scripts/start_pi_camera_stream.sh
```
```bash
sudo killall -9 rpicam-vid
```
### Terminal 10: MQTT Motor Bridge
```bash
export ROS_DOMAIN_ID=30
source ~/ambers_ws/install/setup.bash
ros2 run phoenix_control mqtt_motor_bridge
```
</details>

---

## 🌐 Mosquitto WebSocket Setup (Required for Web Dashboard)
The Web Command Center connects to MQTT via **WebSocket**. Mosquitto must be installed and configured with a WebSocket listener.

1. **Install Mosquitto** (if not already installed) and make sure the configuration directory exists:
   ```bash
   sudo apt update
   sudo apt install -y mosquitto mosquitto-clients
   sudo mkdir -p /etc/mosquitto/conf.d
   ```

2. **Edit the Mosquitto configuration** on the Raspberry Pi:
   ```bash
   sudo nano /etc/mosquitto/conf.d/websocket.conf
   ```
3. **Add the following lines** to the file:
   ```
   # Standard MQTT Port for ROS 2 Nodes
   listener 1883
   protocol mqtt
   allow_anonymous true

   # WebSocket Port for Web UI
   listener 9001
   protocol websockets
   allow_anonymous true
   ```
4. **Restart Mosquitto**:
   ```bash
   sudo systemctl restart mosquitto
   ```
5. **Verify WebSocket is listening**:
   ```bash
   ss -tlnp | grep 9001
   ```

---

## 💻 Laptop Execution
Open a terminal on your **Laptop** and launch:

### 1. Start Fire Detection (Vision Node)
```bash
cd vision_node
pip install -r requirements.txt
python Vision.py
```
> **Tip for offline testing:** `Vision.py` automatically detects when no physical camera is present and will loop a test video file (`.mp4`, `.avi`) or webcam index.

### 2. Web Command Center (Control Pump, Nozzle, Motors)
Open `Phoenix_Web_Command_Center/index.html` in your browser.
1. Go to **⚙ Settings** tab
2. Choose your connection preset:
   - Click **Local Sim (9001)** when testing with Gazebo simulation (`ws://localhost:9001/mqtt`).
   - Click **Robot Pi (Live)** when connecting to the physical robot (`ws://<PI_IP>:9001/mqtt`).
3. Click **⚡ CONNECT TO BROKER**.
4. Switch to **MANUAL** mode to access directional controls, pump, and nozzle.

### 3. Visualize the Map Live (Optional)
Configure your laptop to listen to the same ROS 2 network:
* **Linux:** `export ROS_DOMAIN_ID=30`
* **Windows (Command Prompt):** `set ROS_DOMAIN_ID=30`
* **Windows (PowerShell):** `$env:ROS_DOMAIN_ID=30`

Launch RViz2:
```bash
rviz2
```
In RViz2:
* Set **Fixed Frame** to `map`.
* Add a **Map display** (topic `/map`).
* Add a **RobotModel display**.
* Add a **LaserScan display** (topic `/scan`).
* Add an **Image display** (topic `/camera/image_raw`).

---

## 🚒 How the Mission Works
1. **Fire Detected:** `vision_node/Vision.py` detects a fire, calculates its 3D ray-plane ground intersection ($Z_{world}=0$) relative to the arena, and publishes the navigation coordinate via MQTT.
2. **Nav Goal Triggered:** `mqtt_nav_client` receives the coordinates and sends a `NavigateToPose` goal to Nav2 with target orientation.
3. **Autonomous Navigation:** Nav2 calculates the safest path using the live map, sending movement commands to `motor_controller` (or Gazebo DiffDrive) to drive the robot.
4. **Target Reached:** Once Nav2 confirms the robot is at the fire location (with 0.3m standoff), `mqtt_nav_client` publishes `SUCCEEDED` to `phoenix/status` and fires the `/target_reached` trigger.
5. **Fire Extinguished:** The `pump_controller` activates water suppression spray automatically on arrival or via manual HUD trigger.
6. **Manual Override:** Use the Web Command Center D-Pad, water trigger, and pan-tilt controls to manually override at any point via `mqtt_motor_bridge`.
