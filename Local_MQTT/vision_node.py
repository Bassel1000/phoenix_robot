# Contributor: Amin Mubarak
#3

# Similate the Vision Node for Fire and Human Detection
# This node will publish alerts to the MQTT broker based on random detections.

import paho.mqtt.client as mqtt
import json
import time
import random
import logging

# --- 1. LOGGING SETUP (The Mission Recorder) ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [VISION_NODE] - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("vision_mission.log"), # Saves to VS Code folder
        logging.StreamHandler()                    # Shows in terminal
    ]
)

# --- 2. CONFIGURATION ---
BROKER = "localhost" 
PORT = 1883
TOPIC_HEARTBEAT = "robot/heartbeat"
TOPIC_FIRE = "robot/fire_alert"
TOPIC_HUMAN = "robot/human_alert"

# Initialize MQTT Client
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,"Vision_Node_Sim")

def connect_to_broker():
    try:
        client.connect(BROKER, PORT, 60)
        logging.info(f"Successfully connected to Local Broker at {BROKER}")
    except Exception as e:
        logging.error(f"Failed to connect to Broker: {e}")
        exit(1)

connect_to_broker()

# --- 3. MAIN SIMULATION LOOP ---
logging.info("Starting Mission Simulation...")

try:
    while True:
        # STEP A: Send Heartbeat (The "I am alive" pulse)
        heartbeat_payload = {
            "status": "alive",
            "timestamp": time.time()
        }
        client.publish(TOPIC_HEARTBEAT, json.dumps(heartbeat_payload))
        # We don't log every heartbeat to keep the file clean, 
        # but the robot will know if we stop sending it.

        # STEP B: Simulate Fire Detection (Member #4's part)
        # Randomly decide if fire is seen for testing purposes
        fire_detected = random.random() > 0.8  # 20% chance of fire
        fire_payload = {
            "active": fire_detected,
            "confidence": round(random.uniform(0.85, 0.99), 2) if fire_detected else 0.0,
            "class": "flame" if fire_detected else "none"
        }
        client.publish(TOPIC_FIRE, json.dumps(fire_payload))
        if fire_detected:
            logging.warning(f"SENT: Fire Alert Active! Confidence: {fire_payload['confidence']}")

        # STEP C: Simulate Human Detection (Member #5's part)
        human_detected = random.random() > 0.9 # 10% chance of human
        human_payload = {
            "detected": human_detected,
            "state": random.choice(["conscious", "unconscious"]) if human_detected else "none"
        }
        client.publish(TOPIC_HUMAN, json.dumps(human_payload))
        if human_detected:
            logging.info(f"SENT: Human Detected. State: {human_payload['state']}")

        # Send updates every 2 seconds
        time.sleep(2)

except KeyboardInterrupt:
    logging.info("Vision Node shutting down gracefully...")
    client.disconnect()