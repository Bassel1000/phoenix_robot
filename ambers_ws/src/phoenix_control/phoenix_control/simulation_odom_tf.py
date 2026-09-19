import rclpy
from geometry_msgs.msg import TransformStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from tf2_ros import TransformBroadcaster


class SimulationOdomTf(Node):
    def __init__(self):
        super().__init__("simulation_odom_tf")
        self.tf_broadcaster = TransformBroadcaster(self)
        self.subscription = self.create_subscription(
            Odometry, "/odom", self.odom_callback, 10
        )

    def odom_callback(self, odometry):
        transform = TransformStamped()
        transform.header = odometry.header
        transform.header.frame_id = "odom"
        transform.child_frame_id = "base_footprint"
        transform.transform.translation.x = odometry.pose.pose.position.x
        transform.transform.translation.y = odometry.pose.pose.position.y
        transform.transform.translation.z = odometry.pose.pose.position.z
        transform.transform.rotation.x = odometry.pose.pose.orientation.x
        transform.transform.rotation.y = odometry.pose.pose.orientation.y
        transform.transform.rotation.z = odometry.pose.pose.orientation.z
        transform.transform.rotation.w = odometry.pose.pose.orientation.w
        self.tf_broadcaster.sendTransform(transform)


def main(args=None):
    rclpy.init(args=args)
    node = SimulationOdomTf()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()