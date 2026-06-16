# Phoenix Robot - Execution & Mission Guide

This guide details how to boot up, connect, and run the Phoenix Fire-Fighting Robot in autonomous dynamic mapping mode.

---

## 🔌 Hardware Prerequisites & Wiring
Ensure the Okdo (LD06) LiDAR is connected to the Raspberry Pi 4 GPIO pins exactly as follows:

| LiDAR Wire | Description | Connection on Raspberry Pi |
| :--- | :--- | :--- |
| **VCC** (Blue) | 5V Power | Physical Pin 4 (5V) |
| **GND** (Red) | Ground | Physical Pin 34 (GND) |
| **TX** (Yellow) | Data Output | **Physical Pin 10** (GPIO 15 / RX) |
| **PWM** (White) | Motor Speed | Physical Pin 8 (GPIO 14 / TX) |

---

## 🌐 Network Setup
1. Both your **Laptop** and the **Raspberry Pi** must be connected to the **same Wi-Fi network**.
2. Find the Raspberry Pi's IP address:
   ```bash
   hostname -I
   ```
3. Open `vision.py` on your **Laptop** and change the MQTT connection IP to the Raspberry Pi's IP address:
   ```python
   # Replace with your Pi's actual IP
   client.connect("192.168.1.XX", 1883, 60)
   ```

---

## 🚀 Step-by-Step Run Order (Raspberry Pi)
Open **7 separate terminal windows** on the Raspberry Pi (via SSH). Run the following commands in order:

### Terminal 1: Lidar Publisher (Driver)
Reads raw data from `/dev/ttyAMA0` and publishes `/scan`.
```bash
export ROS_DOMAIN_ID=30
source ~/ambers_ws/install/setup.bash
ros2 run phoenix_control lidar_publisher
```

### Terminal 2: Laser Odometry & Transforms
Publishes the physical transforms (`base_link -> lidar_link`) and computes odometry (`odom -> base_link`) from the Lidar.
```bash
export ROS_DOMAIN_ID=30
source ~/ambers_ws/install/setup.bash
ros2 launch phoenix_description laser_odom.launch.py
```

### Terminal 3: SLAM Toolbox (Dynamic Mapping)
Generates the map on the fly and publishes the `map -> odom` transform.
```bash
export ROS_DOMAIN_ID=30
source ~/ambers_ws/install/setup.bash
ros2 launch slam_toolbox online_async_launch.py slam_params_file:=/home/ambers/ambers_ws/src/phoenix_description/config/mapper_params_online_async.yaml use_sim_time:=False
```

### Terminal 4: Nav2 Stack
Runs the costmaps, path planners, and velocity controllers.
```bash
export ROS_DOMAIN_ID=30
source ~/ambers_ws/install/setup.bash
ros2 launch nav2_bringup navigation_launch.py use_sim_time:=False
```

### Terminal 5: Motor Controller (BTS7960 Driver)
Translates Nav2 velocities (`/cmd_vel`) into PWM voltages to physically drive the motors.
```bash
export ROS_DOMAIN_ID=30
source ~/ambers_ws/install/setup.bash
ros2 run phoenix_control motor_controller
```

### Terminal 6: MQTT Navigation Client
Listens for target coordinates from the laptop over MQTT and triggers Nav2 goals.
```bash
export ROS_DOMAIN_ID=30
source ~/ambers_ws/install/setup.bash
ros2 run phoenix_control mqtt_nav_client
```

### Terminal 7: Extinguishing Hardware
Starts the water pump and fire hose nozzle servos.
```bash
export ROS_DOMAIN_ID=30
source ~/ambers_ws/install/setup.bash
ros2 run phoenix_control pump_controller &
ros2 run phoenix_control nozzle_controller &
```

---

## 💻 Laptop Execution
Open a terminal on your **Laptop** and launch:

### 1. Start Fire Detection (Vision Node)
```bash
python3 vision.py
```

### 2. Visualize the Map Live (Optional)
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

---

## 🚒 How the Mission Works
1. **Fire Detected:** `vision.py` detects a fire on the laptop screen, calculates its 2D coordinates relative to the robot, and publishes it via MQTT.
2. **Nav Goal Triggered:** `mqtt_nav_client` on the Pi receives the coordinates and sends a `NavigateToPose` goal to Nav2.
3. **Autonomous Navigation:** Nav2 calculates the safest path using the live map, sending movement commands to `motor_controller` which spins the wheels.
4. **Target Reached:** Once Nav2 confirms the robot is at the fire location, `mqtt_nav_client` publishes a trigger message.
5. **Fire Extinguished:** The `pump_controller` and `nozzle_controller` activate the pump and direct the water stream to extinguish the fire.
