#1

# Fake Robot Integration Node for Testing MQTT Communication

import paho.mqtt.client as mqtt

def on_message(client, userdata, msg):
    print(f"Topic: {msg.topic} | Data: {msg.payload.decode()}")
    if "true" in msg.payload.decode():
        print(">>> INTEGRATION SUCCESS: Motor Kill-Switch Triggered! <<<")

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,"Simulated_Pi")
client.on_message = on_message
client.connect("localhost", 1883) # Connecting to your Windows Mosquitto
client.subscribe("robot/fire_alert")
client.loop_forever()