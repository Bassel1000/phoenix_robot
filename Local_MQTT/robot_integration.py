# Contributor: Amin Mubarak
#2

# Listens to the messages and decides what the robot should do (The Kill-Switch)
# This node subscribes to the fire and human detection topics. Based on the received alerts, it will print out the corresponding actions (e.g., stopping motors, activating pump, prioritizing rescue path).

import paho.mqtt.client as mqtt
import json
import time
import logging
import threading

# --- 1. LOGGING SETUP (The Robot's Black Box) ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [ROBOT_SYSTEM] - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("robot_mission.log"),
        logging.StreamHandler()
    ]
)

# --- 2. GLOBAL SYSTEM STATE ---
last_heartbeat_time = time.time()
HEARTBEAT_TIMEOUT = 5.0  # Seconds to wait before assuming crash
system_safe = True       # Tracks if connection is healthy

# --- 3. HEARTBEAT WATCHDOG (Tactical Independence Logic) ---
def monitor_connection():
    """Background thread that checks if the Vision Node is still alive."""
    global last_heartbeat_time, system_safe
    
    while True:
        time_since_pulse = time.time() - last_heartbeat_time
        
        if time_since_pulse > HEARTBEAT_TIMEOUT:
            if system_safe:
                logging.critical("!!! NETWORK FAILURE / HEARTBEAT LOST !!!")
                logging.critical(">>> ACTION: EXECUTING FAIL-SAFE (EMERGENCY STOP) <<<")
                system_safe = False # Lock the system until connection returns
        else:
            if not system_safe:
                logging.info("Heartbeat Restored. Re-engaging systems.")
                system_safe = True
        
        time.sleep(1) # Check every second

# --- 4. MQTT CALLBACKS ---
def on_connect(client, userdata, flags, rc, properties):
    logging.info("Robot Node connected to Local Broker.")
    # Subscribe to all mission-critical topics
    client.subscribe([("robot/fire_alert", 0), ("robot/human_alert", 0), ("robot/heartbeat", 0)])

def on_message(client, userdata, msg):
    global last_heartbeat_time
    
    # Always parse payload
    data = json.loads(msg.payload.decode())

    # Topic A: Heartbeat
    if msg.topic == "robot/heartbeat":
        last_heartbeat_time = time.time() # Reset the clock

    # Topic B: Fire Alert
    elif msg.topic == "robot/fire_alert":
        if system_safe: # Only process if connection is healthy
            if data["active"]:
                logging.warning(f"FIRE SIGNAL RECEIVED! Confidence: {data['confidence']}")
                logging.critical(">>> COMMAND: STOP MOTORS | ACTIVATE WATER PUMP")
            else:
                pass # Normal scanning
        else:
            logging.error("Fire alert ignored: System is in Fail-Safe Mode (No connection)")

    # Topic C: Human Alert
    elif msg.topic == "robot/human_alert":
        if system_safe and data["detected"]:
            logging.info(f"HUMAN DETECTED. Status: {data['state']}. Logging for Rescue.")

# --- 5. EXECUTION ---
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,"Robot_Integration_Sim")
client.on_connect = on_connect
client.on_message = on_message

try:
    client.connect("localhost", 1883, 60)
    
    # Start the Watchdog Timer in a separate thread
    watchdog_thread = threading.Thread(target=monitor_connection, daemon=True)
    watchdog_thread.start()
    
    logging.info("Robot Integration Node is active. Monitoring connection...")
    client.loop_forever()

except KeyboardInterrupt:
    logging.info("Robot system shutting down.")