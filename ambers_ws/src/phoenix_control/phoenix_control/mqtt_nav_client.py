# Contributor: Bassel Elbahnasy
import os
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.time import Time
from nav2_msgs.action import NavigateToPose
from std_msgs.msg import Bool
import paho.mqtt.client as mqtt
import json
import math

class MqttNavClient(Node):
    def __init__(self):
        super().__init__('mqtt_nav_client')
        self.get_logger().info("Initializing MQTT to Nav2 Bridge...")
        
        # ROS 2 Action Client for Nav2
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        
        # Publisher to trigger the pump when goal is reached
        self.pump_trigger = self.create_publisher(Bool, 'target_reached', 10)
        
        # Active Goal Tracking to prevent preemption loops
        self.active_goal_x = None
        self.active_goal_y = None
        self.current_goal_handle = None
        
        # MQTT Setup (Supports both paho-mqtt v1.x and v2.x)
        try:
            self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="Nav2_Client")
        except AttributeError:
            self.mqtt_client = mqtt.Client(client_id="Nav2_Client")
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        
        import os
        broker_ip = os.environ.get('MQTT_BROKER_IP', 'localhost')
        
        # Connect to the Broker
        self.mqtt_client.connect(broker_ip, 1883, 60)
        
        # Start MQTT loop in the background
        self.mqtt_client.loop_start()

    def on_connect(self, client, userdata, flags, rc, properties):
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
                    # Cancel any active goal if we are triggering the pump directly
                    if self.current_goal_handle is not None:
                        self.get_logger().info("Canceling active Nav2 goal before starting pump...")
                        self.current_goal_handle.cancel_goal_async()
                    
                    msg_out = Bool()
                    msg_out.data = True
                    self.pump_trigger.publish(msg_out)
                return
            
            # Expecting JSON payload: {"x": 2.5, "y": 1.2, "yaw": 0.5}
            target_x = float(data.get("x", 0.0))
            target_y = float(data.get("y", 0.0))
            
            # Default yaw points from the origin (0,0) to the target if the vision node didn't provide one
            default_yaw = math.atan2(target_y, target_x)
            target_yaw = float(data.get("yaw", default_yaw))
            
            # Check if this goal is already being executed
            if self.active_goal_x is not None and self.active_goal_y is not None:
                dx = target_x - self.active_goal_x
                dy = target_y - self.active_goal_y
                distance = math.sqrt(dx**2 + dy**2)
                
                # If target has not changed significantly, ignore the new MQTT message to prevent preemption
                if distance < 0.10:
                    self.get_logger().info(f"New goal is close to active goal (diff: {distance:.3f}m). Ignoring to prevent preemption.")
                    return
            
            self.send_nav_goal(target_x, target_y, target_yaw)
        except Exception as e:
            self.get_logger().error(f"Failed to parse MQTT message: {e}")

    def send_nav_goal(self, x, y, yaw):
        self.get_logger().info(f"Sending Nav2 goal: x={x}, y={y}, yaw={yaw}")
        self.nav_client.wait_for_server()
        
        # Track the active target coordinates
        self.active_goal_x = x
        self.active_goal_y = y
        
        goal_msg = NavigateToPose.Goal()
        # Set frame_id to base_footprint so coordinates are RELATIVE to the robot's current position!
        # Example: x=0.3 means "drive 30cm forward from where you are right now"
        goal_msg.pose.header.frame_id = 'base_footprint'
        goal_msg.pose.header.stamp = Time().to_msg()
        goal_msg.pose.pose.position.x = x
        goal_msg.pose.pose.position.y = y
        
        # Convert yaw to quaternion so the robot faces the fire
        goal_msg.pose.pose.orientation.z = math.sin(yaw / 2.0)
        goal_msg.pose.pose.orientation.w = math.cos(yaw / 2.0)
        
        self._send_goal_future = self.nav_client.send_goal_async(goal_msg)
        self._send_goal_future.add_done_callback(self.goal_response_callback)

    def goal_response_callback(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().info('Nav2 Goal rejected.')
            # Clear active goal tracker
            self.active_goal_x = None
            self.active_goal_y = None
            return
        self.get_logger().info('Nav2 Goal accepted, navigating...')
        self.current_goal_handle = goal_handle
        self._get_result_future = goal_handle.get_result_async()
        self._get_result_future.add_done_callback(self.get_result_callback)

    def get_result_callback(self, future):
        result = future.result().status
        
        # Clear active goal tracking on completion
        self.active_goal_x = None
        self.active_goal_y = None
        self.current_goal_handle = None
        
        if result == 4: # 4 corresponds to SUCCEEDED
            self.get_logger().info('Navigation Succeeded! Triggering Pump...')
            msg = Bool()
            msg.data = True
            self.pump_trigger.publish(msg)
        else:
            self.get_logger().info(f'Navigation failed with status: {result}')

def main(args=None):
    rclpy.init(args=args)
    node = MqttNavClient()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.mqtt_client.loop_stop()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()