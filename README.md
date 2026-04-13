# Phoenix Robot

Intelligent Mobile Robot for autonomous flame location detection and suppression. This repository utilizes a split-node architecture, distributing tasks across a stationary vision node, a local simulation environment, and the physical edge hardware.

---

## 💻 1. Vision Node Setup (Native Windows / Laptop)
This environment handles the YOLO object detection pipeline and streams the TP-Link Tapo C210 camera feed to track the robot's physical location.

**Prerequisites:** Python 3.8+
1. Navigate to the vision node directory:
   ```bash
   cd vision_node

Install dependencies:

Bash
pip install -r requirements.txt
Run the tracking script:

Bash
python Base_to_Survalience_kinematics.py

🖥️ 2. Simulation & Modeling Setup (WSL / Ubuntu)
This environment is used for testing the ROS 2 Navigation stack and SLAM using Gazebo Harmonic before deploying to physical hardware.

Prerequisites: ROS 2 (Jazzy/Humble) and Gazebo Harmonic.

Navigate to the workspace root:

Bash
cd ambers_ws
Build only the simulation package:

Bash
colcon build --packages-select phoenix_description --symlink-install
Source the workspace:

Bash
source install/setup.bash
Launch the simulation:

Bash
ros2 launch phoenix_description gazebo.launch.py
🍓 3. Mobile Edge Node Setup (Raspberry Pi 5)
This environment runs natively on the robot, handling GPIO pins, UART LiDAR, I2C servos, and the BTS7960 motor drivers.

Prerequisites: ROS 2 installed on the Pi, gpiozero, paho-mqtt, and serial.

Navigate to the workspace root on the Pi:

Bash
cd ambers_ws
Build only the hardware control package:

Bash
colcon build --packages-select phoenix_control --symlink-install
Source the workspace:

Bash
source install/setup.bash
Launch the hardware nodes (Example):

Bash
ros2 run phoenix_control motor_controller
