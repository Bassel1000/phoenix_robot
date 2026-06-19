# Contributor: Bassel Elbahnasy
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from gpiozero import OutputDevice
import paho.mqtt.client as mqtt
import threading

class PumpController(Node):
    def __init__(self):
        super().__init__('pump_controller')
        self.get_logger().info("Initializing Phoenix Pump Controller (Manual Mode)...")
        
        # The relay for the 24V pump is connected to GPIO 26 
        self.pump_relay = OutputDevice(26, active_high=True, initial_value=False)
        
        # MQTT Client Setup for manual control (Supports both paho-mqtt v1.x and v2.x)
        try:
            self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="Pump_Controller")
        except AttributeError:
            self.mqtt_client = mqtt.Client(client_id="Pump_Controller")
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_message = self.on_mqtt_message
        
        import os
        broker_ip = os.environ.get('MQTT_BROKER_IP', 'localhost')
        try:
            self.mqtt_client.connect(broker_ip, 1883, 60)
            self.mqtt_client.loop_start()
            self.get_logger().info("MQTT client connected for pump control.")
        except Exception as e:
            self.get_logger().error(f"Failed to connect to MQTT broker: {e}")

    def on_mqtt_connect(self, client, userdata, flags, rc, properties):
        self.get_logger().info("MQTT connected, subscribing to pump commands...")
        client.subscribe("phoenix/cmd/water")

    def on_mqtt_message(self, client, userdata, msg):
        command = msg.payload.decode().strip().upper()
        self.get_logger().info(f"Received pump command: {command}")
        
        if command == "ON":
            self.pump_relay.on()
            self.get_logger().info("Pump ACTIVATED")
        elif command == "OFF":
            self.pump_relay.off()
            self.get_logger().info("Pump DEACTIVATED")

def main(args=None):
    rclpy.init(args=args)
    node = PumpController()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.pump_relay.off()  # Ensure pump is off on shutdown
        node.mqtt_client.loop_stop()
        node.mqtt_client.disconnect()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()