#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import TransformStamped
from tf2_ros import TransformBroadcaster

class DummyOdomBroadcaster(Node):
    def __init__(self):
        super().__init__('dummy_odom_broadcaster')
        self.br = TransformBroadcaster(self)
        self.timer = self.create_timer(0.1, self.broadcast_timer_callback) # 10Hz loop

    def broadcast_timer_callback(self):
        t = TransformStamped()
        t.header.stamp = self.get_clock().now().to_msg() # Sync clock with live system time
        t.header.frame_id = 'odom'
        t.child_frame_id = 'base_link'
        
        # Keep positions locked at zero
        t.transform.translation.x = 0.0
        t.transform.translation.y = 0.0
        t.transform.translation.z = 0.0
        t.transform.rotation.x = 0.0
        t.transform.rotation.y = 0.0
        t.transform.rotation.z = 0.0
        t.transform.rotation.w = 1.0
        
        self.br.sendTransform(t)

def main():
    rclpy.init()
    node = DummyOdomBroadcaster()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    rclpy.shutdown()

if __name__ == '__main__':
    main()
