# Contributor: Bassel Elbahnasy
# MQTT Motor Bridge: Translates web UI directional commands to Nav2 cmd_vel
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import paho.mqtt.client as mqtt

class MqttMotorBridge(Node):
    def __init__(self):
        super().__init__('mqtt_motor_bridge')
        self.get_logger().info("Initializing MQTT Motor Bridge (Web UI -> cmd_vel)...")
        
        # Publisher for motor commands
        self.cmd_vel_pub = self.create_publisher(Twist, 'cmd_vel', 10)
        
        # Speed configuration
        self.linear_speed = 0.25   # m/s forward/backward
        self.angular_speed = 0.5   # rad/s left/right
        
        # Safety: auto-stop timer if no STOP command received
        self.move_timeout = 0.5  # seconds
        self.last_move_time = None
        self.moving = False
        self.safety_timer = self.create_timer(0.1, self.safety_check)
        
        # MQTT Client Setup
        self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "Motor_Bridge")
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_message = self.on_mqtt_message
        
        try:
            self.mqtt_client.connect("localhost", 1883, 60)
            self.mqtt_client.loop_start()
            self.get_logger().info("MQTT Motor Bridge connected. Listening for web UI commands.")
        except Exception as e:
            self.get_logger().error(f"Failed to connect to MQTT broker: {e}")

    def on_mqtt_connect(self, client, userdata, flags, rc, properties):
        self.get_logger().info("MQTT connected, subscribing to motor commands...")
        client.subscribe("phoenix/cmd/move")

    def on_mqtt_message(self, client, userdata, msg):
        command = msg.payload.decode().strip().upper()
        self.get_logger().info(f"Web UI motor command: {command}")
        
        twist = Twist()
        
        if command == "FORWARD":
            twist.linear.x = self.linear_speed
            self.moving = True
        elif command == "BACKWARD":
            twist.linear.x = -self.linear_speed
            self.moving = True
        elif command == "LEFT":
            twist.angular.z = self.angular_speed
            self.moving = True
        elif command == "RIGHT":
            twist.angular.z = -self.angular_speed
            self.moving = True
        elif command == "STOP":
            # Zero velocity
            self.moving = False
        else:
            self.get_logger().warn(f"Unknown motor command: {command}")
            return
        
        self.cmd_vel_pub.publish(twist)
        if self.moving:
            import time
            self.last_move_time = time.time()

    def safety_check(self):
        """Auto-stop if no command received for move_timeout seconds."""
        if self.moving and self.last_move_time is not None:
            import time
            elapsed = time.time() - self.last_move_time
            if elapsed > self.move_timeout:
                self.get_logger().info("Safety timeout: auto-stopping motors.")
                twist = Twist()  # Zero velocity
                self.cmd_vel_pub.publish(twist)
                self.moving = False

def main(args=None):
    rclpy.init(args=args)
    node = MqttMotorBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        # Send stop command on shutdown
        twist = Twist()
        node.cmd_vel_pub.publish(twist)
        node.mqtt_client.loop_stop()
        node.mqtt_client.disconnect()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()
