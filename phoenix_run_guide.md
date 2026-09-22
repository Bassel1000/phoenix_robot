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

### 📦 Prerequisites (WSL2 / Linux)
Before running the simulation for the first time, ensure all necessary packages and the high-performance DDS middleware are installed:

```bash
# 1. Install required Python drivers and CycloneDDS RMW
sudo apt update
sudo apt install -y python3-paho-mqtt python3-gpiozero ros-jazzy-rmw-cyclonedds-cpp mosquitto mosquitto-clients

# 2. Set CycloneDDS as the default RMW in your shell (fixes WSL2 DDS multicast discovery)
echo "export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp" >> ~/.bashrc
source ~/.bashrc
```
> [!NOTE]
> **Why CycloneDDS?** By default, FastDDS Simple Discovery can fail between separate WSL2 terminal processes due to multicast packet isolation. `rmw_cyclonedds_cpp` ensures seamless inter-process communication across Gazebo, Nav2, and ROS 2 CLI tools. `simulation.launch.py` also automatically configures this in the node environment.

---

### Step 1: Start Mosquitto Broker with WebSockets
The Web Command Center communicates with the robot via MQTT over WebSockets on port `9001`, while ROS 2 nodes communicate via standard MQTT on port `1883`.

- **If Mosquitto is running as a Windows Service:**
  Ensure `C:\Program Files\mosquitto\mosquitto.conf` contains:
  ```conf
  listener 1883
  protocol mqtt
  allow_anonymous true

  listener 9001
  protocol websockets
  allow_anonymous true
  ```
  Open PowerShell as Administrator and restart the service:
  ```powershell
  Restart-Service mosquitto
  ```

- **If running inside Linux / WSL2:**
  ```bash
  sudo systemctl restart mosquitto
  # Or test in the foreground with verbose logs:
  mosquitto -c /etc/mosquitto/conf.d/websocket.conf -v
  ```

---

### Step 2: Launch Gazebo Harmonic Simulation & Full ROS Stack
Open a WSL2 or Linux terminal:
```bash
source /opt/ros/jazzy/setup.bash
cd /mnt/d/Phoenix/ambers_ws
source install/setup.bash

# Option A: Launch High-Fidelity Datacenter Environment (Recommended for Demos & Competitions)
ros2 launch phoenix_description simulation.launch.py world_type:=datacenter pro_model:=true

# Option B: Launch High-Bay Warehouse Environment
ros2 launch phoenix_description simulation.launch.py world_type:=warehouse pro_model:=true

# Option C: Fully Automated Hands-Free Competition Demo Run (Automatic 6-Stage Mission)
ros2 launch phoenix_description simulation.launch.py world_type:=datacenter pro_model:=true run_demo:=true
```

* **What this runs:**
  - **Gazebo Harmonic:** Spawns `phoenix_datacenter_world.sdf` (42U server racks, cold aisle, crash-cart obstacle, technician casualty, burning UPS server fire) or `phoenix_warehouse_world.sdf`.
  - **Phoenix Pro Robot Model:** Spawns the upgraded Phoenix Pro model with Deep Metallic Crimson livery, Sky-Blue anodized wheel hubs, obsidian 2020 extrusion arch, Okdo LD06 TOF LiDAR, and front 2-DOF suppression turret.
  - **ros_gz_bridge:** Bridges `/clock`, `/scan`, `/cmd_vel`, `/odom`, and `/camera/image_raw`.
  - **Dynamic Odometry Broadcaster:** Publishes `odom -> base_footprint` TF.
  - **SLAM Toolbox:** Initializes asynchronous online mapping.
  - **MQTT Control Bridges:** Starts `mqtt_motor_bridge`, `mqtt_nav_client`, `pump_controller`, and `nozzle_controller` with `use_sim_time:=True`.
  - **Automatic Nav2 Delay:** Nav2 is delayed by **18 seconds** to allow SLAM Toolbox and the TF tree (`map -> odom -> base_footprint`) to stabilize before costmaps initialize.

> [!IMPORTANT]
> **Wait 18 Seconds on Startup!**
> You will see: `Nav2 launch delayed by 18.0 seconds to allow SLAM Toolbox & TF to stabilize...`
> Wait until the terminal logs show Nav2 lifecycle managers reaching the **active** state (`Nav2 is active and ready`) before sending autonomous navigation goals.

---

### Step 3: Connect Web Command Center
1. Open `Phoenix_Web_Command_Center/index.html` in your web browser (Chrome, Edge, Firefox).
2. Click the **⚙ Settings** tab on the left sidebar.
3. Click the **"Local Sim (9001)"** preset button (sets broker to `ws://localhost:9001/mqtt`).
4. Click **⚡ CONNECT TO BROKER**. The top status badge will immediately turn green: `SYSTEM ACTIVE` and `MQTT ONLINE`.
5. Toggle the mode switch in the topbar or sidebar to **MANUAL**.

---

### Step 4: Test Manual Driving (D-Pad Teleoperation)
1. In the Web Command Center with mode set to **MANUAL**, locate the **DIRECTIONAL CONTROLS (D-PAD)**.
2. Click and **HOLD DOWN** any directional button:
   - **▲ FORWARD:** Drives robot forward at $0.35\text{ m/s}$.
   - **▼ REVERSE:** Reverses robot at $0.35\text{ m/s}$.
   - **◀ ROTATE LEFT:** Rotates robot counter-clockwise at $0.8\text{ rad/s}$.
   - **▶ ROTATE RIGHT:** Rotates robot clockwise at $0.8\text{ rad/s}$.
3. **Continuous Driving:** While holding the button, the HUD sends a 150ms heartbeat pulse to `ambers/robot/control`. The `mqtt_motor_bridge` feeds `/cmd_vel`, and the robot moves smoothly in the Gazebo 3D viewport.
4. **Instant Stop:** Releasing the button sends a `STOP` command, immediately halting the robot.
5. You can also test the **HOLD TO SPRAY** water button and **NOZZLE GIMBAL** pan/tilt sliders.

---

### Step 5: Test Autonomous Navigation Goal
Once the 20-second Nav2 startup window has passed:

- **Option A (Click-to-Navigate via Web Command Center Minimap):**
  1. In the Web Command Center with mode set to **MANUAL**, look at the **▸ ARENA WAYPOINT MAP**.
  2. Simply **click anywhere** inside the arena canvas!
  3. A green waypoint pin drops at that coordinate, and the robot immediately calculates a trajectory and navigates to that exact spot in Gazebo!
  4. You can also click the quick presets: **🔥 Fire (2.2, 1.8)**, **🛡 Flank (0.8, 1.5)**, or **🏠 Origin (0, 0)**.

- **Option B (Point-and-Click in RViz2 with "2D Goal Pose"):**
  1. Open RViz2 (or launch simulation with `rviz:=true`).
  2. In the top RViz2 toolbar, click the **"2D Goal Pose"** tool.
  3. Click anywhere on the map or 3D floor and drag the green arrow to set the desired arrival heading.
  4. Release the mouse. Nav2 immediately computes the global path and drives the robot in Gazebo in real-time!

- **Option C (Via MQTT Target Topic):**
  From any terminal:
  ```bash
  mosquitto_pub -h localhost -p 1883 -t "ambers/robot/navigation/target" -m '{"x": 2.2, "y": 1.8, "frame_id": "map"}'
  ```

- **Option D (Via ROS 2 Action CLI):**
  ```bash
  ros2 action send_goal /navigate_to_pose nav2_msgs/action/NavigateToPose \
    "{pose: {header: {frame_id: map}, pose: {position: {x: 2.2, y: 1.8}, orientation: {w: 1.0}}}}"
  ```

---

### 📡 Visualizing the LiDAR Scan

You can visualize the live 360° laser scans in two ways:

#### Method 1: Directly in Gazebo Harmonic GUI (Zero Extra Terminals)
Gazebo Harmonic includes a built-in LiDAR visualizer plugin:
1. In the Gazebo simulation window, look at the top-right menu and click the **three vertical dots (⋮)** $\to$ **Plugins**.
2. Select **"Visualize Lidar"** from the dropdown.
3. A panel appears on the right. Under the **Sensor** dropdown, select `/scan` or `lidar_sensor`.
4. Check the box to activate visualization.
5. The 3D laser beams and reflection points will be drawn directly inside the Gazebo 3D viewport, showing rays sweeping the arena walls and objects in real time!

#### Method 2: In RViz2 (Full 3D SLAM & Robot View - Recommended)
The simulation bridge publishes the laser scan to the standard ROS 2 topic `/scan` (`sensor_msgs/msg/LaserScan`). We have created a pre-configured RViz display profile ([`phoenix_sim.rviz`](file:///d:/Phoenix/ambers_ws/src/phoenix_description/config/phoenix_sim.rviz)) matching the Cybernetic Ember & Steel theme.

- **Option A: Auto-launch with Simulation:**
  Add `rviz:=true` to your launch command:
  ```bash
  ros2 launch phoenix_description simulation.launch.py rviz:=true
  ```

- **Option B: Open RViz2 in a Separate Terminal:**
  While the simulation is running:
  ```bash
  source /opt/ros/jazzy/setup.bash
  source /mnt/d/Phoenix/ambers_ws/install/setup.bash
  ros2 run rviz2 rviz2 -d $(ros2 pkg prefix phoenix_description)/share/phoenix_description/config/phoenix_sim.rviz
  ```

* **What you see in RViz2:**
  - **Sky-Blue Laser Scan (`/scan`):** Real-time 360° point cloud with 0.04m square points accurately mapping obstacle boundaries.
  - **Live Dynamic Map (`/map`):** The 2D occupancy grid dynamically mapped and updated by SLAM Toolbox as the robot drives.
  - **Robot 3D Model (`/robot_description`):** Complete Phoenix URDF chassis, wheels, and camera assembly with live TF transformations (`map -> odom -> base_footprint -> lidar_link`).



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
