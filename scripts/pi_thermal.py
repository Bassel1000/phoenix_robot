import os
import time
import json
import paho.mqtt.client as mqtt

# Configuration
BROKER = "192.168.1.100"  # Replace with the IP address of your MQTT Broker (laptop IP)
PORT = 1883               # Default MQTT port
TOPIC = "robot/temperature"
INTERVAL = 2.0            # Seconds between temperature updates

def get_pi_temperature():
    try:
        # Read the thermal zone file as requested
        temp_str = os.popen("cat /sys/class/thermal/thermal_zone0/temp").read().strip()
        if temp_str:
            # The value is usually in millidegrees Celsius
            temp_c = float(temp_str) / 1000.0
            return temp_c
        return None
    except Exception as e:
        print(f"Error reading temperature: {e}")
        return None

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"Connected to MQTT Broker at {BROKER}")
    else:
        print(f"Failed to connect, return code {rc}")

def main():
    print("Starting Raspberry Pi Thermal Telemetry...")
    
    client = mqtt.Client("pi_thermal_publisher")
    client.on_connect = on_connect
    
    try:
        client.connect(BROKER, PORT, 60)
    except Exception as e:
        print(f"Error connecting to MQTT Broker: {e}")
        print("Please ensure you have set the BROKER variable to your laptop's IP address.")
        return

    client.loop_start()

    try:
        while True:
            temp = get_pi_temperature()
            if temp is not None:
                payload = json.dumps({"temperature": round(temp, 1)})
                client.publish(TOPIC, payload)
                print(f"Published {payload} to {TOPIC}")
            time.sleep(INTERVAL)
    except KeyboardInterrupt:
        print("Exiting...")
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()
