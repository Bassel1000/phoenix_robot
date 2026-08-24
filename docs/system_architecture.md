# 🏗️ System Architecture & Distributed Node Topology

The **Phoenix Robot** is architected on a distributed, three-tier compute model designed to maximize real-time edge performance while leveraging off-board compute for intensive computer vision and centralized mission oversight.

---

## 🌐 Distributed Topology Overview

```mermaid
flowchart TB
    subgraph Stationary_Node ["🖥️ Stationary Vision Node (Laptop / Workstation)"]
        direction TB
        V_CAM["Tapo C200 Surveillance Feed\n(RTSP 1080p Stream)"] --> VP["AI Vision Engine\n(PyTorch Flame CNN + Keras Life/Fall)"]
        VP --> ARUCO["ArUco Spatial Transformer\n(cv2.solvePnP Pose Estimator)"]
        ARUCO --> V_MQTT["Vision MQTT Client\n(Paho MQTT v2)"]
        FLASK["Flask Video Stream Server\n(Port 5000: /video_feed_tapo, /video_feed_pi)"]
    end

    subgraph Edge_Node ["🤖 Mobile Edge Node (Raspberry Pi 4B)"]
        direction TB
        MB["Mosquitto MQTT Broker\n(Port 1883: TCP | Port 9001: WebSockets)"]
        
        subgraph ROS2_Stack ["ROS 2 Humble / Jazzy Stack"]
            LIDAR["LiDAR Driver Node\n(Okdo LD06 UART)"]
            RF2O["rf2o Laser Odometry\n(/scan ➔ /odom)"]
            SLAM["SLAM Toolbox\n(Online Async 2D Mapping)"]
            NAV2["Nav2 Navigation Stack\n(Costmaps, Planner, Controller)"]
            
            M_CTRL["Motor Controller Node\n(BTS7960 Dual H-Bridge PWM)"]
            P_CTRL["Pump Controller Node\n(24V Relay Driver)"]
            N_CTRL["Nozzle Controller Node\n(2-DOF Pan-Tilt Servos)"]
            
            NAV_CLI["MQTT Nav Client Node\n(Action Client: NavigateToPose)"]
            M_BRIDGE["MQTT Motor Bridge Node\n(Manual Override ➔ /cmd_vel)"]
        end
        
        PI_CAM["Raspberry Pi Camera Stream\n(rpicam-vid MJPEG Server)"]
    end

    subgraph Operator_Console ["🎮 Operator Web Command Center (Browser)"]
        UI["Tactical HUD Dashboard\n(HTML5 / CSS3 / Vanilla JS)"]
        WS_CLIENT["MQTT.js WebSocket Client\n(ws://&lt;PI_IP&gt;:9001/mqtt)"]
        CAM_HUD["Dual-Camera Stream HUD\n(Surveillance + FPV Feeds)"]
    end

    %% Network Connections
    V_MQTT -- "1. Target Coordinates [ambers/robot/navigation/target]" --> MB
    MB -- "2. Goal Dispatch" --> NAV_CLI
    NAV_CLI -- "3. NavigateToPose Action" --> NAV2
    NAV2 -- "/cmd_vel" --> M_CTRL

    LIDAR -- "/scan" --> RF2O
    LIDAR -- "/scan" --> SLAM
    LIDAR -- "/scan" --> NAV2
    RF2O -- "/odom" --> SLAM
    RF2O -- "/odom" --> NAV2

    WS_CLIENT -- "Manual Drive [phoenix/cmd/move]" --> MB
    MB --> M_BRIDGE
    M_BRIDGE -- "/cmd_vel" --> M_CTRL

    WS_CLIENT -- "Water Spray [phoenix/cmd/water]" --> MB
    MB --> P_CTRL

    WS_CLIENT -- "Nozzle Pan/Tilt [phoenix/cmd/nozzle]" --> MB
    MB --> N_CTRL

    NAV_CLI -- "Telemetry [ambers/robot/status]" --> MB
    MB --> WS_CLIENT
    MB --> V_MQTT

    PI_CAM -. "FPV Video Stream" .-> CAM_HUD
    FLASK -. "Surveillance Annotated Stream" .-> CAM_HUD
```

---

## 📦 Core Compute Nodes

### 1. Stationary Vision Node (Laptop / Base Station)
* **High-Throughput Perception:** Runs heavy convolutional neural networks (PyTorch & TensorFlow/Keras) for simultaneous fire detection, human presence detection, and fall/casualty recognition.
* **Spatial Calibration:** Tracks the robot's real-time position and orientation within the global arena via an ArUco marker array mounted to the robot's chassis.
* **Coordinate Projection:** Translates 2D bounding boxes in camera pixel coordinates to metric 3D arena coordinates, publishing navigation waypoints to the robot.
* **Stream Transcoding:** Hosts a lightweight Flask multi-threaded HTTP server (port `5000`) broadcasting annotated MJPEG video feeds.

### 2. Mobile Edge Node (Raspberry Pi 4B)
* **Autonomous Navigation:** Executes the complete ROS 2 robotics stack including 2D SLAM, laser odometry, global/local costmaps, and trajectory planners.
* **Hardware Actuation:** Direct GPIO hardware interface driving high-current BTS7960 motor bridges, high-pressure pump relays, and precision pan-tilt servos.
* **Central Broker:** Runs the local Mosquitto MQTT message broker serving both native TCP connections (ROS 2 nodes) and WebSocket clients (Web Dashboard).
* **FPV Video Server:** Streams high-definition, low-latency video directly from the robot-mounted Pi Camera.

### 3. Operator Web Command Center (Browser Console)
* **Single-Pane-of-Glass HUD:** Provides real-time mission telemetry, navigation feedback, active fire alerts, and dual-camera monitoring.
* **Instant Manual Override:** Grants the operator fine-grained manual control over drive motors, nozzle gimbal orientation, and water suppression activation.
* **Zero-Install Client:** Runs entirely in any standard modern web browser with zero local dependencies using MQTT over WebSockets.

---

## 📡 MQTT Topic Specification & Message Payloads

The communication backbone uses Mosquitto MQTT for lightweight, low-latency telemetry and command transport:

| Topic | Publisher | Subscriber | Payload Format | Description |
| :--- | :--- | :--- | :--- | :--- |
| `phoenix/cmd/move` | Web Console | `mqtt_motor_bridge` | String: `FORWARD` \| `BACKWARD` \| `LEFT` \| `RIGHT` \| `STOP` | Manual drive control override |
| `phoenix/cmd/water` | Web Console | `pump_controller` | String: `ON` \| `OFF` | Hold-to-spray 24V water pump relay trigger |
| `phoenix/cmd/nozzle` | Web Console | `nozzle_controller` | String: `LEFT` \| `RIGHT` \| `UP` \| `DOWN` \| `STOP` \| `CENTER` | 2-DOF Pan-Tilt servo positioning |
| `ambers/robot/navigation/target` | Vision Node | `mqtt_nav_client` | JSON: `{"x": float, "y": float}` | Flame navigation target coordinate (meters) |
| `ambers/robot/status` | `mqtt_nav_client` | Vision Node / Web Console | JSON: `{"status": string}` | Mission status (`NAVIGATING`, `TARGET_REACHED`, `IDLE`) |

---

## 🧭 Coordinate Transforms & TF2 Tree

The robot maintains a standard ROS 2 transform tree to ensure spatial consistency across laser scan matching, odometry, and navigation planning:

```mermaid
graph TD
    map["map (Global Fixed Frame)"] -->|SLAM Toolbox| odom["odom (Odometry Frame)"]
    odom -->|rf2o_laser_odometry| base_footprint["base_footprint (Ground Projection)"]
    base_footprint -->|Fixed Joint| base_link["base_link (Robot Physical Center)"]
    base_link -->|Fixed Joint| laser_frame["laser_frame (LiDAR Sensor Origin)"]
    base_link -->|Fixed Joint| camera_link["camera_link (Pi Camera Origin)"]
    base_link -->|Joint Transform| pan_link["pan_link (Gimbal Yaw)"]
    pan_link -->|Joint Transform| tilt_link["tilt_link (Nozzle Pitch)"]
```

### Key Reference Frames:
* **`map`**: The global static coordinate frame established by SLAM Toolbox during initial mapping.
* **`odom`**: The continuous, drift-compensated odometry frame generated by `rf2o_laser_odometry`.
* **`base_footprint`**: 2D ground projection of the robot body.
* **`base_link`**: Center of mass of the robot chassis ($465\text{ mm} \times 355\text{ mm} \times 200\text{ mm}$).
* **`laser_frame`**: Optical center of the Okdo LD06 LiDAR sensor.

---

## 🔐 Safety & Failsafe Mechanisms

1. **Deadman Safety Watchdog:** In manual mode, directional movement commands automatically time out if no update is received within 500ms, preventing runaway robot behavior.
2. **Hold-to-Spray Interlock:** Water suppression requires an active, continuous press on the trigger; releasing the button immediately de-energizes the 24V pump relay.
3. **Stand-Off Safe Distance:** The autonomous navigation client automatically locks movement once within `0.30 m` (30 cm) of the flame target, eliminating collision risks with the fire source.
4. **Isolated Power Rails:** The 24V pump motor circuit and 12V drive motor circuits are optically and galvanically isolated from the Raspberry Pi 4 logic board.
