import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose
from std_msgs.msg import Bool
import paho.mqtt.client as mqtt
import json

class MqttNavClient(Node):
    def __init__(self):
        super().__init__('mqtt_nav_client')
        self.get_logger().info("Initializing MQTT to Nav2 Bridge...")
        
        # ROS 2 Action Client for Nav2
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        
        # Publisher to trigger the pump when goal is reached
        self.pump_trigger = self.create_publisher(Bool, 'target_reached', 10)
        
        # MQTT Setup [cite: 426, 917]
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        
        # Replace with your HiveMQ Cloud credentials
        self.mqtt_client.tls_set()
        self.mqtt_client.username_pw_set("phoenix", "Ambers2026")
        self.mqtt_client.connect("b3a389a5b99d452c856bdd2af40b564f.s1.eu.hivemq.cloud", 8883, 60)
        
        # Start MQTT loop in the background
        self.mqtt_client.loop_start()

    def on_connect(self, client, userdata, flags, rc):
        self.get_logger().info(f"Connected to HiveMQ with result code {rc}")
        client.subscribe("ambers/robot/navigation/target") # Update topic as needed

    def on_message(self, client, userdata, msg):
        self.get_logger().info(f"Received MQTT Message: {msg.payload.decode()}")
        try:
            # Expecting JSON payload: {"x": 2.5, "y": 1.2} [cite: 481]
            data = json.loads(msg.payload.decode())
            target_x = float(data.get("x", 0.0))
            target_y = float(data.get("y", 0.0))
            
            self.send_nav_goal(target_x, target_y)
        except Exception as e:
            self.get_logger().error(f"Failed to parse MQTT message: {e}")

    def send_nav_goal(self, x, y):
        self.get_logger().info(f"Sending Nav2 goal: x={x}, y={y}")
        self.nav_client.wait_for_server()
        
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose.header.frame_id = 'map'
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
        goal_msg.pose.pose.position.x = x
        goal_msg.pose.pose.position.y = y
        goal_msg.pose.pose.orientation.w = 1.0 # Assuming facing forward is fine
        
        self._send_goal_future = self.nav_client.send_goal_async(goal_msg)
        self._send_goal_future.add_done_callback(self.goal_response_callback)

    def goal_response_callback(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().info('Nav2 Goal rejected.')
            return
        self.get_logger().info('Nav2 Goal accepted, navigating...')
        self._get_result_future = goal_handle.get_result_async()
        self._get_result_future.add_done_callback(self.get_result_callback)

    def get_result_callback(self, future):
        result = future.result().status
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