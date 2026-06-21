# Contributor: Bassel Elbahnasy
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from rclpy.qos import qos_profile_sensor_data
import serial
import math
import threading
import time

class LidarPublisher(Node):
    def __init__(self):
        super().__init__('lidar_publisher')
        self.get_logger().info("Initializing Decoupled Okdo LiDAR Publisher...")
        
        self.publisher_ = self.create_publisher(LaserScan, 'scan', qos_profile_sensor_data)
        
        # Use a short timeout of 10ms for non-blocking serial reads
        self.serial_port = serial.Serial('/dev/ttyAMA0', baudrate=230400, timeout=0.01)
        
        # Buffer and ranges configuration
        self.serial_buffer = bytearray()
        self.current_ranges = [0.0] * 360 
        
        # Background thread setup for reading and parsing
        self.running = True
        self.read_thread = threading.Thread(target=self.read_loop)
        self.read_thread.daemon = True
        self.read_thread.start()
        
        # ROS 2 Timer for stable 10Hz publishing
        self.timer = self.create_timer(0.1, self.publish_scan)

    def read_loop(self):
        while self.running and rclpy.ok():
            try:
                # Read all available bytes from serial
                in_waiting = self.serial_port.in_waiting
                if in_waiting > 0:
                    raw_bytes = self.serial_port.read(in_waiting)
                    self.parse_lidar_data(raw_bytes)
                else:
                    time.sleep(0.005) # Sleep 5ms to keep CPU low
            except Exception as e:
                self.get_logger().error(f"Error in LiDAR read loop: {e}")
                time.sleep(0.1)

    def parse_lidar_data(self, raw_bytes):
        self.serial_buffer.extend(raw_bytes)
        
        # Process as long as we have at least one full packet (47 bytes)
        while len(self.serial_buffer) >= 47:
            if self.serial_buffer[0] == 0x54 and self.serial_buffer[1] == 0x2C:
                packet = self.serial_buffer[:47]
                
                # Start and End angles are in 0.01 degree units, little-endian
                start_angle = int.from_bytes(packet[4:6], byteorder='little') / 100.0
                end_angle = int.from_bytes(packet[42:44], byteorder='little') / 100.0
                
                # Calculate the angular step size between the 12 points
                diff = end_angle - start_angle
                if diff < 0:
                    diff += 360.0
                step = diff / 11.0 # 12 points = 11 intervals
                
                # Extract the 12 distance measurements
                for i in range(12):
                    point_angle = (start_angle + i * step) % 360.0
                    idx = 6 + i * 3
                    distance_mm = int.from_bytes(packet[idx:idx+2], byteorder='little')
                    distance_m = distance_mm / 1000.0
                    
                    # 1. RPLiDAR spins clockwise, but ROS expects counter-clockwise. (Mirror)
                    # 2. The LiDAR's physical right side (90 degrees) is facing the front. (Shift)
                    # Formula: ros_angle = (450.0 - point_angle) % 360.0
                    ros_angle = (450.0 - point_angle) % 360.0
                    degree_idx = int(round(ros_angle)) % 360
                    
                    # Filter 0.0 which RPLiDAR uses for invalid/missing readings.
                    # We also filter anything below 0.15m (the hardware minimum range)
                    if distance_m == 0.0 or distance_m < 0.15:
                        self.current_ranges[degree_idx] = 0.0 
                    else:
                        self.current_ranges[degree_idx] = distance_m
                
                self.serial_buffer = self.serial_buffer[47:]
            else:
                try:
                    next_header = self.serial_buffer.index(0x54)
                    if next_header > 0:
                        self.serial_buffer = self.serial_buffer[next_header:]
                    else:
                        self.serial_buffer.pop(0)
                except ValueError:
                    self.serial_buffer.clear()
                    break

    def publish_scan(self):
        scan_msg = LaserScan()
        # Use the ROS node clock for timing
        scan_msg.header.stamp = self.get_clock().now().to_msg()
        scan_msg.header.frame_id = 'lidar_link'
        scan_msg.angle_min = 0.0
        scan_msg.angle_max = 359.0 * math.pi / 180.0
        scan_msg.angle_increment = math.pi / 180.0 
        scan_msg.range_min = 0.15 
        scan_msg.range_max = 10.0  
        scan_msg.ranges = list(self.current_ranges) # Make a copy to avoid concurrent writes
        
        self.publisher_.publish(scan_msg)

def main(args=None):
    rclpy.init(args=args)
    node = LidarPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.running = False
        if hasattr(node, 'read_thread'):
            node.read_thread.join(timeout=1.0)
        node.serial_port.close()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()