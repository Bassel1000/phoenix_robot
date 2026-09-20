import os
import sys
import time
import math
import subprocess
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Twist

class FastNavVerifier(Node):
    def __init__(self):
        super().__init__('fast_nav_verifier')
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self.odom_sub = self.create_subscription(Odometry, '/odom', self.odom_cb, 10)
        self.cmd_sub = self.create_subscription(Twist, '/cmd_vel', self.cmd_cb, 10)

        self.current_x = 0.0
        self.current_y = 0.0
        self.current_yaw = 0.0
        self.max_cmd_vx = 0.0
        self.max_cmd_wz = 0.0
        self.max_odom_vx = 0.0
        self.max_odom_wz = 0.0
        self.goal_done = False
        self.goal_result_status = None

    def odom_cb(self, msg):
        self.current_x = msg.pose.pose.position.x
        self.current_y = msg.pose.pose.position.y
        qx = msg.pose.pose.orientation.x
        qy = msg.pose.pose.orientation.y
        qz = msg.pose.pose.orientation.z
        qw = msg.pose.pose.orientation.w
        siny_cosp = 2.0 * (qw * qz + qx * qy)
        cosy_cosp = 1.0 - 2.0 * (qy * qy + qz * qz)
        self.current_yaw = math.atan2(siny_cosp, cosy_cosp)

        vx = abs(msg.twist.twist.linear.x)
        wz = abs(msg.twist.twist.angular.z)
        if vx > self.max_odom_vx:
            self.max_odom_vx = vx
        if wz > self.max_odom_wz:
            self.max_odom_wz = wz

    def cmd_cb(self, msg):
        vx = abs(msg.linear.x)
        wz = abs(msg.angular.z)
        if vx > self.max_cmd_vx:
            self.max_cmd_vx = vx
        if wz > self.max_cmd_wz:
            self.max_cmd_wz = wz

    def wait_for_nav2(self, timeout=45.0):
        self.get_logger().info("Waiting for NavigateToPose action server...")
        start = time.time()
        while not self.nav_client.wait_for_server(timeout_sec=2.0):
            rclpy.spin_once(self, timeout_sec=0.1)
            if time.time() - start > timeout:
                return False
        return True

    def send_goal(self, x, y, yaw):
        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = 'map'
        goal.pose.header.stamp = self.get_clock().now().to_msg()
        goal.pose.pose.position.x = float(x)
        goal.pose.pose.position.y = float(y)
        goal.pose.pose.orientation.z = math.sin(yaw / 2.0)
        goal.pose.pose.orientation.w = math.cos(yaw / 2.0)

        self.get_logger().info(f"Dispatching goal: x={x}, y={y}, target_yaw={yaw:.3f} rad ({yaw*180/math.pi:.1f} deg)")
        future = self.nav_client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, future)
        handle = future.result()
        if not handle.accepted:
            self.get_logger().error("Goal rejected by Nav2!")
            return False

        self.get_logger().info("Goal accepted by Nav2. Monitoring navigation trajectory...")
        result_future = handle.get_result_async()
        
        start_time = time.time()
        last_log = time.time()
        while rclpy.ok():
            rclpy.spin_once(self, timeout_sec=0.1)
            if result_future.done():
                result = result_future.result()
                self.goal_result_status = result.status
                self.goal_done = True
                break
            if time.time() - start_time > 60.0:
                self.get_logger().warn("Navigation timed out after 60 seconds.")
                break
            if time.time() - last_log > 2.0:
                self.get_logger().info(
                    f"Pose: ({self.current_x:.2f}, {self.current_y:.2f}), "
                    f"Yaw: {self.current_yaw*180/math.pi:.1f}°, "
                    f"Max Cmd Vx: {self.max_cmd_vx:.2f} m/s, Max Cmd Wz: {self.max_cmd_wz:.2f} rad/s"
                )
                last_log = time.time()
        return self.goal_done

def main():
    rclpy.init()
    node = FastNavVerifier()

    if not node.wait_for_nav2(timeout=60.0):
        print("FAIL: Nav2 server did not become available.")
        node.destroy_node()
        rclpy.shutdown()
        sys.exit(1)

    target_x = 2.0
    target_y = 1.5
    target_yaw = 0.785 # 45 degrees, aiming directly at fire at (2.5, 2.0)

    success = node.send_goal(target_x, target_y, target_yaw)

    dist_err = math.hypot(node.current_x - target_x, node.current_y - target_y)
    yaw_err_deg = abs((node.current_yaw - target_yaw + math.pi) % (2 * math.pi) - math.pi) * 180.0 / math.pi

    print("========================================")
    print("FAST FIRE NAVIGATION BENCHMARK RESULTS")
    print("========================================")
    print(f"Goal Completed: {success}")
    print(f"Max Commanded Linear Velocity : {node.max_cmd_vx:.2f} m/s (previous cap: 0.35 m/s)")
    print(f"Max Commanded Angular Velocity: {node.max_cmd_wz:.2f} rad/s (previous cap: 1.0 rad/s)")
    print(f"Max Odometry Linear Velocity  : {node.max_odom_vx:.2f} m/s")
    print(f"Final Robot Position: ({node.current_x:.3f}, {node.current_y:.3f}) [Target: ({target_x}, {target_y})]")
    print(f"Position Error: {dist_err:.3f} m")
    print(f"Final Robot Heading: {node.current_yaw*180/math.pi:.1f}° [Target: {target_yaw*180/math.pi:.1f}°]")
    print(f"Heading Alignment Error to Fire: {yaw_err_deg:.2f}°")
    print("========================================")

    node.destroy_node()
    rclpy.shutdown()

    if dist_err < 0.35 and node.max_cmd_vx > 0.5:
        print("BENCHMARK PASSED!")
        sys.exit(0)
    else:
        print("BENCHMARK FAILED or INCOMPLETE.")
        sys.exit(1)

if __name__ == '__main__':
    main()
