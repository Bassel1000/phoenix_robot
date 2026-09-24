# 🎮 Phoenix Web Command Center

The **Phoenix Web Command Center** is a zero-install, browser-based tactical HUD and telemetry dashboard engineered for the Phoenix autonomous emergency response robot.

---

## 🌟 Key Features

* **Dual-Stream Tactical HUD:** Real-time side-by-side surveillance stream (with neural bounding boxes and tracking vectors) and forward-facing robot FPV feed.
* **Instant Mode Switching:** Seamless toggle between full **Autonomous Mode** and low-latency **Manual Override**.
* **Virtual Flight-Deck Controls:** On-screen D-Pad, variable speed sliders, 2-DOF pan-tilt turret joystick, and tactile hold-to-spray water cannon trigger.
* **Real-Time Telemetry & Gauges:** Monitors speed, heading, battery voltages, Wi-Fi signal strength, and mission event logs.
* **Zero-Install Client:** Powered by MQTT over WebSockets (`ws://<BROKER_IP>:9001/mqtt`), running in any modern desktop or mobile browser.

---

## 🚀 Quickstart

### 1. Launch MQTT Broker
Ensure Mosquitto is running with WebSocket support enabled on port `9001` (see [`mosquitto.conf`](../mosquitto.conf)):

```bash
mosquitto -c mosquitto.conf
```

### 2. Open the HUD
Simply open `index.html` in your web browser:
```bash
# Directly in browser:
open index.html
# Or serve via a lightweight HTTP server:
python -m http.server 8080
```

### 3. Connect
1. Navigate to the **⚙ Settings** modal in the HUD.
2. Select your connection target:
   * **Local Sim (9001):** `ws://localhost:9001/mqtt` for Gazebo simulation.
   * **Robot Pi (Live):** `ws://<PI_IP>:9001/mqtt` for the physical robot.
3. Click **⚡ CONNECT TO BROKER**.

---

## 📁 Directory Layout

```
Phoenix_Web_Command_Center/
├── index.html        # Main tactical HUD interface
├── logs.html         # Historical mission log viewer
├── styles.css        # Cybernetic Ember & Obsidian UI styling
├── script.js         # MQTT client, HUD state machine & telemetry logic
├── mqtt.min.js       # Paho MQTT JavaScript client
└── images/           # Web interface assets
    └── phoenix_logo_fire.svg  # Animated SVG fire emblem
```