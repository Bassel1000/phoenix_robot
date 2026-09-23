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
        
        # Speed configuration (parameterized for smooth, stable teleoperation)
        self.declare_parameter('linear_speed', 0.65)
        self.declare_parameter('angular_speed', 3.50)
        self.linear_speed = float(self.get_parameter('linear_speed').value)
        self.angular_speed = float(self.get_parameter('angular_speed').value)
        
        # Safety: auto-stop timer if no STOP command received
        self.move_timeout = 0.5  # seconds
        self.last_move_time = None
        self.moving = False
        self.safety_timer = self.create_timer(0.1, self.safety_check)
        
        # MQTT Client Setup (Supports both paho-mqtt v1.x and v2.x)
        try:
            self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="Motor_Bridge")
        except AttributeError:
            self.mqtt_client = mqtt.Client(client_id="Motor_Bridge")
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_mqtt_message
        
        import os
        broker_ip = os.environ.get('MQTT_BROKER_IP', 'localhost')
        try:
            self.mqtt_client.connect(broker_ip, 1883, 60)
            self.mqtt_client.loop_start()
            self.get_logger().info("MQTT Motor Bridge connected. Listening for web UI commands.")
        except Exception as e:
            self.get_logger().error(f"Failed to connect to MQTT broker: {e}")

    def on_connect(self, client, userdata, flags, rc, properties=None):
        self.get_logger().info("MQTT connected, subscribing to motor commands...")
        client.subscribe("phoenix/cmd/move")
        client.subscribe("phoenix/cmd/speed")

    def on_mqtt_message(self, client, userdata, msg):
        payload_str = msg.payload.decode().strip()
        
        # Dynamic speed adjustment from Web UI (MANUAL Mode)
        if msg.topic == "phoenix/cmd/speed":
            try:
                new_speed = float(payload_str)
                if 0.1 <= new_speed <= 1.0:
                    self.linear_speed = new_speed
                    # Skid-steer kinematics: wheel_speed = angular * B / 2 = angular * 0.175
                    # Scale angular speed proportionally so turning matches linear drive authority
                    self.angular_speed = min(new_speed * 5.0, 5.0)
                    self.get_logger().info(f"Updated manual teleop speed: linear={self.linear_speed:.2f} m/s, angular={self.angular_speed:.2f} rad/s")
            except ValueError:
                pass
            return

        command = payload_str.upper()
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
            # Zero velocity burst for instantaneous stop response
            self.moving = False
            self.last_move_time = None
            for _ in range(3):
                self.cmd_vel_pub.publish(twist)
            return
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
