# Contributor: Bassel Elbahnasy
import os
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.time import Time
from nav2_msgs.action import NavigateToPose
from std_msgs.msg import Bool
from geometry_msgs.msg import PoseStamped
import paho.mqtt.client as mqtt
import json
import math
import random
import string

class MqttNavClient(Node):
    def __init__(self):
        super().__init__('mqtt_nav_client')
        self.get_logger().info("Initializing MQTT to Nav2 Bridge...")
        
        # ROS 2 Action Client for Nav2
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        
        # Publisher to trigger the pump when goal is reached
        self.pump_trigger = self.create_publisher(Bool, 'target_reached', 10)
        
        # Generate a random suffix for the MQTT Client ID to avoid conflicts if multiple instances run
        client_suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=4))
        self.mqtt_client_id = f"Nav2_Client_{client_suffix}"
        
        # Active Goal Tracking to prevent preemption loops
        self.active_goal_x = None
        self.active_goal_y = None
        self.current_goal_handle = None
        self.control_mode = "MANUAL"
        self.e_stop_latched = False
        self.cmd_vel_pub = self.create_publisher(Twist, 'cmd_vel', 10)
        
        # MQTT Setup (Supports both paho-mqtt v1.x and v2.x)
        try:
            self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self.mqtt_client_id)
        except AttributeError:
            self.mqtt_client = mqtt.Client(client_id=self.mqtt_client_id)
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        
        import os
        broker_ip = os.environ.get('MQTT_BROKER_IP', 'localhost')
        
        # Connect to the Broker
        self.mqtt_client.connect(broker_ip, 1883, 60)
        
        # Start MQTT loop in the background
        self.mqtt_client.loop_start()

    def on_connect(self, client, userdata, flags, rc, properties=None):
        self.get_logger().info(f"Connected to Local Broker with result code {rc}")
        client.subscribe("ambers/robot/navigation/target")
        client.subscribe("ambers/robot/navigation/cancel")
        client.subscribe("ambers/robot/pump")
        client.subscribe("phoenix/cmd/move")
        client.subscribe("phoenix/mode")

    def on_message(self, client, userdata, msg):
        payload_raw = msg.payload.decode().strip()
        self.get_logger().info(f"Received MQTT Message on {msg.topic}: {payload_raw}")
        
        # Mode Switch Handler
        if msg.topic == "phoenix/mode":
            self.control_mode = payload_raw.upper()
            self.get_logger().info(f"Nav2 Bridge: Mode switched to {self.control_mode}")
            if self.control_mode == "MANUAL":
                if self.current_goal_handle is not None:
                    self.current_goal_handle.cancel_goal_async()
                    self.current_goal_handle = None
                self.active_goal_x = None
                self.active_goal_y = None
                for _ in range(3):
                    self.cmd_vel_pub.publish(Twist())
            return

        # Immediate Nav2 Goal Cancellation / E-Stop Handler
        if msg.topic in ["ambers/robot/navigation/cancel", "phoenix/cmd/move"]:
            cmd = payload_raw.upper()
            if cmd in ["STOP", "CANCEL"] or msg.topic == "ambers/robot/navigation/cancel":
                self.e_stop_latched = True
                self.get_logger().warn(f"E-STOP LATCHED via {msg.topic}. Canceling active Nav2 goal...")
                if self.current_goal_handle is not None:
                    self.current_goal_handle.cancel_goal_async()
                    self.current_goal_handle = None
                self.active_goal_x = None
                self.active_goal_y = None
                for _ in range(5):
                    self.cmd_vel_pub.publish(Twist())
                self.publish_status("GOAL_CANCELED", {"message": "Active navigation goal canceled by operator / E-Stop."})
                return
            elif cmd in ["FORWARD", "BACKWARD", "LEFT", "RIGHT", "UNLATCH"]:
                self.e_stop_latched = False
                return
            else:
                return

        try:
            data = json.loads(payload_raw)
            
            if msg.topic == "ambers/robot/pump":
                trigger = data.get("activate", False)
                if trigger:
                    self.get_logger().info("Received MQTT Pump trigger. Activating pump...")
                    if self.current_goal_handle is not None:
                        self.get_logger().info("Canceling active Nav2 goal before starting pump...")
                        self.current_goal_handle.cancel_goal_async()
                        self.current_goal_handle = None
                    
                    msg_out = Bool()
                    msg_out.data = True
                    self.pump_trigger.publish(msg_out)
                return
            
            # Guard against E-Stop
            if self.e_stop_latched:
                self.get_logger().warn("Navigation target REJECTED: E-Stop is currently latched.")
                return

            # Coordinates are map-frame positions unless a different frame is explicit.
            target_x = float(data.get("x", 0.0))
            target_y = float(data.get("y", 0.0))
            target_frame = str(data.get("frame_id", "map"))
            
            # If explicit yaw is provided, use it directly.
            if "yaw" in data and data["yaw"] is not None:
                target_yaw = float(data["yaw"])
            elif math.hypot(2.5 - target_x, 2.0 - target_y) < 1.5:
                target_yaw = math.atan2(2.0 - target_y, 2.5 - target_x)
            elif target_x < 0 and target_y == 0:
                target_yaw = 0.0
            else:
                target_yaw = math.atan2(target_y, target_x)
            
            # Anti-Preemption Gate: Don't cancel active trajectory if target has not shifted significantly (>0.45m)
            if self.current_goal_handle is not None and self.active_goal_x is not None and self.active_goal_y is not None:
                dx = target_x - self.active_goal_x
                dy = target_y - self.active_goal_y
                distance = math.sqrt(dx**2 + dy**2)
                
                if distance < 0.45:
                    self.get_logger().info(f"Active goal in progress (shift: {distance:.3f}m < 0.45m). Ignoring to prevent path oscillation.")
                    return
            
            self.send_nav_goal(target_x, target_y, target_yaw, target_frame)
        except Exception as e:
            self.get_logger().error(f"Failed to parse MQTT message: {e}")

    def send_nav_goal(self, x, y, yaw, frame_id):
        self.get_logger().info(
            f"Sending Nav2 goal: x={x}, y={y}, yaw={yaw}, frame={frame_id}"
        )
        if not self.nav_client.wait_for_server(timeout_sec=4.0):
            self.get_logger().warn("Nav2 action server not yet ready! (Waiting for Nav2 bringup)")
            self.publish_status("NAV2_INITIALIZING", {"message": "Nav2 is still initializing. Please retry in a few seconds."})
            return
        
        # Track the active target coordinates
        self.active_goal_x = x
        self.active_goal_y = y
        
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose.header.frame_id = frame_id
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
        goal_msg.pose.pose.position.x = float(x)
        goal_msg.pose.pose.position.y = float(y)
        goal_msg.pose.pose.orientation.z = math.sin(yaw / 2.0)
        goal_msg.pose.pose.orientation.w = math.cos(yaw / 2.0)
        
        self._send_goal_future = self.nav_client.send_goal_async(goal_msg)
        self._send_goal_future.add_done_callback(self.goal_response_callback)

    def publish_status(self, state, extra=None):
        payload = {"status": state}
        if extra:
            payload.update(extra)
        try:
            msg_str = json.dumps(payload)
            self.mqtt_client.publish("phoenix/status", msg_str)
            self.mqtt_client.publish("ambers/robot/status", msg_str)
            self.get_logger().info(f"Published status to MQTT: {msg_str}")
        except Exception as e:
            self.get_logger().warn(f"Failed to publish status: {e}")

    def goal_response_callback(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().info('Nav2 Goal rejected.')
            self.publish_status("REJECTED")
            # Clear active goal tracker
            self.active_goal_x = None
            self.active_goal_y = None
            return
        self.get_logger().info('Nav2 Goal accepted, navigating...')
        self.publish_status("NAVIGATING", {"x": self.active_goal_x, "y": self.active_goal_y})
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
            self.get_logger().info('Navigation Succeeded! Standoff target reached.')
            self.publish_status("SUCCEEDED", {"reached": True})
            msg = Bool()
            msg.data = True
            self.pump_trigger.publish(msg)
        else:
            self.get_logger().info(f'Navigation failed with status: {result}')
            self.publish_status(f"FAILED", {"status_code": result})

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
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()