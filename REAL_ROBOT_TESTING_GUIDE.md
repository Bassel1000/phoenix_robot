# 🔥 Phoenix Physical Robot — Real-Time Testing & Deployment Guide

> **Confidential Team Document**  
> *Target Audience:* Hardware integration engineer / Base station operator testing the real robot.  
> *Note:* This guide contains hardware-specific bringup instructions for testing the physical Phoenix platform without requiring a Tapo C210 camera.

---

## 📑 Table of Contents
1. [System Architecture & Roles](#1-system-architecture--roles)
2. [Pre-Flight Hardware Checklist](#2-pre-flight-hardware-checklist)
3. [Phone Camera Setup (Tapo C210 Alternative)](#3-phone-camera-setup-tapo-c210-alternative)
4. [Step-by-Step Bringup Sequence](#4-step-by-step-bringup-sequence)
5. [Real-Time Verification & Test Stages](#5-real-time-verification--test-stages)
6. [Emergency Procedures & Safety Interlocks](#6-emergency-procedures--safety-interlocks)
7. [Hardware Troubleshooting Matrix](#7-hardware-troubleshooting-matrix)

---

## 1. System Architecture & Roles

The physical Phoenix testing setup consists of two computing nodes and one overhead vision sensor communicating over a local Wi-Fi network:

```
┌────────────────────────────────┐         ┌───────────────────────────────┐
│     OVERHEAD SMARTPHONE        │         │      STATIONARY LAPTOP        │
│  (Tapo Alternative / 1080p)    │         │       (Base Station)          │
│  Landscape, elevated mount     │         │                               │
│  Stream: RTSP or DroidCam      │         │  1. Vision.py (AI Inference)  │
└───────────────┬────────────────┘         │  2. Web Command Center HUD    │
                │ Video Stream             └───────────────▲───────────────┘
                ▼                                          │ MQTT / Video
┌──────────────────────────────────────────────────────────┴───────────────┐
│                           LOCAL WI-FI ROUTER / HOTSPOT                    │
└──────────────────────────────────────────▲───────────────────────────────┘
                                           │ MQTT (1883 / 9001) + ROS 2
                                           ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                   ROBOT CHASSIS — RASPBERRY PI 4B                         │
│  • Okdo LD06 TOF LiDAR (/scan)        • RF2O Laser Odometry (/odom)      │
│  • SLAM Toolbox (2D /map)             • Nav2 High-Speed MPPI Controller  │
│  • 2x BTS7960 Motor Drivers (4WD)     • Pan/Tilt Nozzle Gimbal Servos    │
│  • 24V Diaphragm Pump + 5V Relay      • Mosquitto MQTT Broker            │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Pre-Flight Hardware Checklist

Complete this checklist before applying main battery power:

- [ ] **Common Ground:** Verify that Raspberry Pi GND, 12V battery GND, 24V battery GND, and UBEC step-down GNDs are all connected to the **central ground bus**.
- [ ] **LiDAR Connectivity:** Okdo LD06 connected to Pi Header:
  - Blue Wire $\to$ `Pin 4 (+5V)`
  - Red Wire $\to$ `Pin 6 (GND)`
  - Yellow Wire $\to$ `Pin 12 (GPIO 18 / RXD0)`
  - White Wire $\to$ `Pin 10 (GPIO 15 / PWM)`
- [ ] **Motor Drivers (BTS7960):**
  - Left Motor FWD $\to$ `GPIO 17 (Pin 11)` | Left REV $\to$ `GPIO 27 (Pin 13)`
  - Right Motor FWD $\to$ `GPIO 25 (Pin 22)` | Right REV $\to$ `GPIO 23 (Pin 16)`
  - Motor power terminals connected securely to 12V Battery.
- [ ] **Suppression Actuators:**
  - Water Pump Relay signal $\to$ `GPIO 26 (Pin 37)`.
  - Pan Servo (360° continuous) $\to$ `GPIO 19 (Pin 35)`.
  - Tilt Servo (180° positional) $\to$ `GPIO 13 (Pin 33)`.
  - Water reservoir filled and primer tube cleared of air bubbles.
- [ ] **ArUco Marker:**
  - Standard $10\text{ cm} \times 10\text{ cm}$ ArUco marker (`DICT_4X4_50`, ID 1, 2, 3, or 4) affixed flat on top of the robot chassis with forward heading aligned.

---

## 3. Phone Camera Setup (Tapo C210 Alternative)

You do **not** need the Tapo C210 camera. You can use any smartphone (Android or iOS).

### Option A: Virtual Webcam via USB/Wi-Fi with DroidCam (Recommended: Lowest Latency)
1. Install **DroidCam** on the phone and the **DroidCam Client** on the laptop.
2. Connect phone via USB cable (enable USB Debugging) or Wi-Fi.
3. In DroidCam Client, connect to the phone. The phone now acts as a standard webcam.
4. Mount the phone horizontally (Landscape) on a tripod or shelf overlooking the arena.
5. In your laptop terminal:
   ```bash
   # If laptop has no built-in webcam:
   export RTSP_URL="0"
   # If laptop has a built-in webcam at index 0:
   export RTSP_URL="1"
   ```

### Option B: Wi-Fi Stream with IP Webcam (Android)
1. Install **IP Webcam** (by Pavel Khlebovich) from Google Play Store.
2. In the app, scroll to the bottom and tap **Start Server**.
3. Note the displayed IP address (e.g., `http://192.168.1.105:8080`).
4. Mount the phone horizontally overlooking the arena.
5. In your laptop terminal:
   ```bash
   export RTSP_URL="http://192.168.1.105:8080/video"
   ```

> [!TIP]
> Keep the phone plugged into a charger and turn off screen timeout / sleep mode during testing.

---

## 4. Step-by-Step Bringup Sequence

Follow this exact order to avoid startup races:

### Step 1: Start Raspberry Pi (Robot Edge)
> [!TIP]
> For complete details on connecting via Laptop Hotspot, Phone Hotspot, or Direct LAN, refer to the [Robot Networking & Hotspot Guide](file:///c:/Education/KSIU/Graduation_Project/phoenix_robot/phoenix_robot/ROBOT_NETWORKING_GUIDE.md).

SSH into the Raspberry Pi from your laptop:
```bash
ssh ambers@<ROBOT_IP>   # e.g., ssh ambers@192.168.137.163 or ssh ambers@ambers-desktop.local
# Or if using default Raspberry Pi OS:
# ssh pi@<ROBOT_IP>
```

1. **Verify MQTT Broker:**
   ```bash
   sudo systemctl status mosquitto
   # If not running:
   sudo systemctl start mosquitto
   ```

2. **Build and Source ROS 2 Workspace:**
   ```bash
   cd ~/Phoenix/ambers_ws   # or your workspace directory
   colcon build --packages-select phoenix_control phoenix_description --symlink-install
   source install/setup.bash
   ```

3. **Launch Physical Robot Stack:**
   ```bash
   ros2 launch phoenix_description phoenix_bringup.launch.py
   ```
   > [!IMPORTANT]
   > **Wait 15 Seconds:** Nav2 has an intentional 15-second delay to let LiDAR odometry and SLAM Toolbox establish the transform chain (`map -> odom -> base_footprint`). Wait until you see `Nav2 is active and ready`.

---

### Step 2: Start Base Station Vision Node (Laptop)
On the laptop running the AI models:

```bash
cd Phoenix
# Activate python environment if using venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Set Environment Variables:
# 1. Point to your phone camera stream:
export RTSP_URL="http://192.168.1.105:8080/video"  # or "0" / "1" for DroidCam
# 2. Point to the Raspberry Pi MQTT Broker:
export MQTT_BROKER="<ROBOT_IP>"

# Launch Vision Engine:
python vision_node/Vision.py
```

* This starts the PyTorch flame CNN, YOLOv8 detector, HSV candle filter, ArUco 3D PnP solver, and Flask streaming server on port `5000`.
* A preview window titled `Vision Node: Tapo Tracking & AI` will pop up.

---

### Step 3: Launch Phoenix Web Command Center
1. On your laptop, open `Phoenix_Web_Command_Center/index.html` in Google Chrome or Edge.
2. In the left navigation menu, click **⚙ Settings**.
3. Under **BROKER CONFIGURATION**:
   - **Broker Address:** Enter your Raspberry Pi IP: `ws://<ROBOT_IP>:9001/mqtt`
4. Under **VIDEO STREAM CONFIGURATION**:
   - **Surveillance Feed:** `http://localhost:5000/video_feed_tapo`
   - **Forward FPV Feed:** `http://localhost:5000/video_feed_pi`
5. Click **⚡ CONNECT TO BROKER**.
   - The top header indicator will switch to **SYSTEM ACTIVE** and **MQTT ONLINE**.

---

## 5. Real-Time Verification & Test Stages

Perform tests in the following progression:

### Stage 1: Manual Teleoperation & Actuators
1. In the Web Command Center topbar, set mode to **MANUAL**.
2. **D-Pad Driving Test:**
   - Click and hold **▲ FORWARD**: All 4 wheels should rotate forward.
   - Click and hold **▼ REVERSE**: All 4 wheels should rotate backward.
   - Click and hold **◀ ROTATE LEFT**: Left wheels reverse, right wheels go forward.
   - Click and hold **▶ ROTATE RIGHT**: Right wheels reverse, left wheels go forward.
   - Release: Robot must immediately halt.
3. **Nozzle Gimbal Test:**
   - Drag the **Pan Slider** ($0^\circ \to 360^\circ$): Nozzle turret pans horizontally.
   - Drag the **Tilt Slider** ($0^\circ \to 90^\circ$): Nozzle tilts up and down.
4. **Suppression Pump Test:**
   - Click and hold **HOLD TO SPRAY**: Relay on GPIO 26 clicks ON and water pump engages. Releasing immediately stops the pump.

---

### Stage 2: LiDAR & Laser Odometry Verification
From an SSH terminal on the Pi:
```bash
# 1. Check LiDAR raw data rate (should be 10-15 Hz):
ros2 topic hz /scan

# 2. Check RF2O laser odometry rate:
ros2 topic hz /odom

# 3. Check transform chain:
ros2 run tf2_ros tf2_echo map odom
ros2 run tf2_ros tf2_echo odom base_footprint
```
* **Arena Mapping:** In MANUAL mode, drive the robot around the test arena once. SLAM Toolbox will build the 2D occupancy grid in the background.

---

### Stage 3: Vision & Spatial Coordinate Calibration
1. Ensure the robot is placed inside the arena with the ArUco marker visible in the phone camera window.
2. Check the OpenCV window:
   - Green bounding box and coordinate axes $[X_r, Y_r, Z_r]$ should overlay the robot.
3. Light a small candle or test flame in the arena:
   - The vision node will draw a detection box labeled `Fire` or `Fire (HSV)`.
   - Look at the terminal: it will print calculated ground coordinates:
     ```text
     Target Fire World Coordinates: X = 2.15 m, Y = 1.40 m
     ```
   - These coordinates are automatically dispatched to topic `ambers/robot/navigation/target`.

---

### Stage 4: Full Autonomous Extinguishing Mission
1. On the Web Command Center, toggle mode to **AUTONOMOUS** (or click the fire icon on the radar minimap).
2. **Autonomous Trajectory:**
   - Nav2 MPPI controller calculates the global trajectory avoiding obstacles.
   - Robot accelerates up to $0.80\text{ m/s}$ towards the fire.
   - Robot halts automatically at a safe **$0.30\text{ m}$ standoff distance** with nozzle facing the flame.
3. **Suppression Activation:**
   - The robot publishes `target_reached` on ROS 2 and status `ARRIVED` on MQTT.
   - Water pump engages and extinguishes the flame.

---

## 6. Emergency Procedures & Safety Interlocks

If the robot behaves erratically or approaches an obstacle too quickly:

1. **Immediate Web E-Stop:** Click the **EMERGENCY STOP** button on the bottom-right of the Web Command Center (sends immediate zero-velocity command).
2. **Terminal Hard-Stop:**
   ```bash
   mosquitto_pub -h <ROBOT_IP> -t "phoenix/cmd/move" -m "STOP"
   mosquitto_pub -h <ROBOT_IP> -t "phoenix/cmd/water" -m "OFF"
   ```
3. **Hardware Power Cut:** Flip the main toggle switch on the 12V battery harness.

---

## 7. Hardware Troubleshooting Matrix

| Symptom | Probable Cause | Corrective Action |
| :--- | :--- | :--- |
| **Robot drives backward when pressing FORWARD** | Motor polarity reversed | Swap the RPWM and LPWM pin assignments in `phoenix_control/motor_controller.py` or invert motor wires on the driver. |
| **Phone stream fails to open in Vision.py** | Wrong IP address or firewall block | Verify phone and laptop can ping each other (`ping <phone_ip>`). Check that RTSP/HTTP URL matches the app display. |
| **ArUco marker not detected** | Glare, poor lighting, or resolution | Increase room lighting, avoid direct reflections on marker laminate, ensure marker ID is 1, 2, 3, or 4. |
| **Web Command Center shows "MQTT OFFLINE"** | Mosquitto websocket port 9001 closed | Check `/etc/mosquitto/conf.d/phoenix.conf` has `listener 9001` and `protocol websockets`. Restart Mosquitto. |
| **Robot stutters during autonomous navigation** | Costmap obstacle clearing or slow SLAM | Keep wheel speed smooth; ensure LiDAR lens is clean. Check `ros2 topic hz /scan` is $\ge 10\text{ Hz}$. |
| **Pump does not spray water** | Air lock in pump or low battery | Prime the pump by siphoning water into the intake tube; verify 24V battery voltage $\ge 22.0\text{V}$. |
