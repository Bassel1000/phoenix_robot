# Contributor: Bassel Elbahnasy
import os
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool
from sensor_msgs.msg import LaserScan
import paho.mqtt.client as mqtt
import json
import math
import threading
import time

class MqttNavClient(Node):
    def __init__(self):
        super().__init__('mqtt_nav_client')
        self.get_logger().info("Initializing MQTT Dead-Reckoning Bridge...")
        
        # Publisher for motor commands
        self.cmd_vel_pub = self.create_publisher(Twist, 'cmd_vel', 10)
        
        # Publisher to trigger the pump when goal is reached
        self.pump_trigger = self.create_publisher(Bool, 'target_reached', 10)
        
        # Subscriber for LiDAR obstacle avoidance
        self.scan_sub = self.create_subscription(LaserScan, 'scan', self.scan_callback, qos_profile_sensor_data)
        self.obstacle_detected = False
        self.safety_distance = 0.45 # meters. Stop if anything is closer than this!
        
        # --- DEAD RECKONING CALIBRATION ---
        # Since we are ignoring the LiDAR, we calculate time = distance / speed.
        # These numbers must match the physical capabilities of your robot. 
        # If the robot travels too far, increase these numbers (it thinks it's moving slower than it is).
        # If it doesn't travel far enough, decrease these numbers.
        self.linear_speed = 0.5   # Virtual m/s
        self.angular_speed = 0.5  # Virtual rad/s
        # ----------------------------------
        
        self.is_executing = False
        
        # MQTT Setup (Supports both paho-mqtt v1.x and v2.x)
        try:
            self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="Nav2_Client")
        except AttributeError:
            self.mqtt_client = mqtt.Client(client_id="Nav2_Client")
            
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        
        broker_ip = os.environ.get('MQTT_BROKER_IP', 'localhost')
        self.mqtt_client.connect(broker_ip, 1883, 60)
        self.mqtt_client.loop_start()

    def scan_callback(self, msg):
        # Check the cone directly in front of the robot (approx +/- 20 degrees)
        # Assuming angle 0 is forward, indices 0-20 and 340-359.
        front_ranges = []
        
        # Some lidars have inf or NaN for out of range, we must filter them
        for i in range(0, 20):
            if i < len(msg.ranges) and 0.1 < msg.ranges[i] < 10.0:
                front_ranges.append(msg.ranges[i])
                
        for i in range(len(msg.ranges) - 20, len(msg.ranges)):
            if 0 <= i < len(msg.ranges) and 0.1 < msg.ranges[i] < 10.0:
                front_ranges.append(msg.ranges[i])
                
        if front_ranges:
            min_dist = min(front_ranges)
            if min_dist < self.safety_distance:
                if not self.obstacle_detected:
                    self.get_logger().warn(f"OBSTACLE AHEAD! Distance: {min_dist:.2f}m")
                self.obstacle_detected = True
            else:
                self.obstacle_detected = False
        else:
            self.obstacle_detected = False

    def on_connect(self, client, userdata, flags, rc, properties=None):
        self.get_logger().info(f"Connected to Local Broker with result code {rc}")
        client.subscribe("ambers/robot/navigation/target") # Update topic as needed
        client.subscribe("ambers/robot/pump")

    def on_message(self, client, userdata, msg):
        self.get_logger().info(f"Received MQTT Message on {msg.topic}: {msg.payload.decode()}")
        try:
            data = json.loads(msg.payload.decode())
            
            if msg.topic == "ambers/robot/pump":
                trigger = data.get("activate", False)
                if trigger:
                    self.get_logger().info("Received MQTT Pump trigger. Activating pump...")
                    self.is_executing = False # cancel any running movements
                    msg_out = Bool()
                    msg_out.data = True
                    self.pump_trigger.publish(msg_out)
                return
            
            if self.is_executing:
                self.get_logger().info("Already executing a movement. Ignoring new target.")
                return

            # Expecting JSON payload: {"x": 2.5, "y": 1.2, "yaw": 0.5}
            target_x = float(data.get("x", 0.0))
            target_y = float(data.get("y", 0.0))
            
            # Default yaw points from the origin (0,0) to the target
            default_yaw = math.atan2(target_y, target_x)
            target_yaw = float(data.get("yaw", default_yaw))
            
            # Distance to move
            distance = math.sqrt(target_x**2 + target_y**2)
            
            # Start dead reckoning sequence in a background thread to avoid blocking ROS
            self.is_executing = True
            threading.Thread(target=self.execute_dead_reckoning, args=(distance, target_yaw)).start()
            
        except Exception as e:
            self.get_logger().error(f"Failed to parse MQTT message: {e}")

    def execute_dead_reckoning(self, distance, yaw):
        self.get_logger().info(f"Starting dead-reckoning: dist={distance:.2f}m, turn={yaw:.2f}rad")
        twist = Twist()
        
        # 1. Turn to face the target
        if abs(yaw) > 0.05:
            turn_time = abs(yaw) / self.angular_speed
            twist.angular.z = self.angular_speed if yaw > 0 else -self.angular_speed
            
            self.get_logger().info(f"Turning for {turn_time:.2f}s")
            
            # Keep publishing to satisfy the new watchdog timer in motor_controller!
            start_time = time.time()
            while time.time() - start_time < turn_time and self.is_executing:
                self.cmd_vel_pub.publish(twist) 
                time.sleep(0.1)
                
            # Stop turning
            twist.angular.z = 0.0
            self.cmd_vel_pub.publish(twist)
            time.sleep(0.5) # brief pause to settle
            
        # 2. Drive forward
        if distance > 0.01 and self.is_executing:
            drive_time = distance / self.linear_speed
            twist.linear.x = self.linear_speed
            
            self.get_logger().info(f"Driving forward for {drive_time:.2f}s")
            
            # Keep publishing to satisfy the new watchdog timer in motor_controller!
            start_time = time.time()
            while time.time() - start_time < drive_time and self.is_executing:
                if self.obstacle_detected:
                    self.get_logger().error("EMERGENCY STOP: Obstacle Avoidance Triggered!")
                    self.is_executing = False
                    break
                    
                self.cmd_vel_pub.publish(twist) 
                time.sleep(0.1)
                
            # Stop driving
            twist.linear.x = 0.0
            self.cmd_vel_pub.publish(twist)
            
        if self.is_executing:
            self.get_logger().info("Target reached via dead-reckoning! Triggering pump...")
            msg = Bool()
            msg.data = True
            self.pump_trigger.publish(msg)
            
        self.is_executing = False

def main(args=None):
    rclpy.init(args=args)
    node = MqttNavClient()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.is_executing = False
        node.mqtt_client.loop_stop()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()