# Contributor: Bassel Elbahnasy
import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool
import paho.mqtt.client as mqtt
import threading

class PumpController(Node):
    def __init__(self):
        super().__init__('pump_controller')
        self.get_logger().info("Initializing Phoenix Pump Controller...")
        
        # The relay for the 24V pump is connected to GPIO 26 
        try:
            from gpiozero import OutputDevice
            self.pump_relay = OutputDevice(26, active_high=True, initial_value=False)
            self.get_logger().info("Physical GPIO 26 relay initialized for pump.")
        except Exception as e:
            self.get_logger().warn(f"Hardware GPIO not available for pump (simulation/headless mode): {e}")
            self.pump_relay = None
            
        # ROS 2 subscription to autonomous suppression triggers
        self.target_sub = self.create_subscription(Bool, 'target_reached', self.target_reached_callback, 10)
        
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

    def on_mqtt_connect(self, client, userdata, flags, rc, properties=None):
        self.get_logger().info("MQTT connected, subscribing to pump commands...")
        client.subscribe("phoenix/cmd/water")

    def target_reached_callback(self, msg):
        if msg.data:
            self.get_logger().info("Received target_reached trigger. Ready for suppression.")

    def set_pump_state(self, active: bool):
        if self.pump_relay is not None:
            if active:
                self.pump_relay.on()
            else:
                self.pump_relay.off()
        self.get_logger().info(f"Pump state set to: {'ON' if active else 'OFF'}")

    def on_mqtt_message(self, client, userdata, msg):
        command = msg.payload.decode().strip().upper()
        self.get_logger().info(f"Received pump command: {command}")
        
        if command == "ON":
            self.set_pump_state(True)
        elif command == "OFF":
            self.set_pump_state(False)

def main(args=None):
    rclpy.init(args=args)
    node = PumpController()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.set_pump_state(False)  # Ensure pump is off on shutdown
        node.mqtt_client.loop_stop()
        node.mqtt_client.disconnect()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()