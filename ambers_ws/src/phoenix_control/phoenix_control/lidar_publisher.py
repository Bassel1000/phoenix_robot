# Contributor: Bassel Elbahnasy
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
import serial
import math

class LidarPublisher(Node):
    def __init__(self):
        super().__init__('lidar_publisher')
        self.get_logger().info("Initializing Okdo LiDAR Publisher...")
        
        self.publisher_ = self.create_publisher(LaserScan, 'scan', 10)
        
        # Standard UART setup for Raspberry Pi GPIO serial
        self.serial_port = serial.Serial('/dev/ttyAMA0', baudrate=230400, timeout=1.0)
        
        # Buffer to hold incomplete serial frames
        self.serial_buffer = bytearray()
        
        # Array to hold the most recent distance for 360 discrete degrees
        self.current_ranges = [0.0] * 360 
        
        # Timer to read serial and publish at ~10Hz
        self.timer = self.create_timer(0.1, self.publish_scan)

    def publish_scan(self):
        raw_data = self.serial_port.read_all()
        
        if not raw_data:
            return

        # Decode the byte stream
        ranges = self.parse_lidar_data(raw_data) 
        
        scan_msg = LaserScan()
        scan_msg.header.stamp = self.get_clock().now().to_msg()
        scan_msg.header.frame_id = 'lidar_link'
        scan_msg.angle_min = 0.0
        scan_msg.angle_max = 2 * math.pi
        
        # 1 degree increment in radians
        scan_msg.angle_increment = math.pi / 180.0 
        
        scan_msg.range_min = 0.35 # Calibrated to ignore robot chassis
        scan_msg.range_max = 10.0  # 10m max distance
        scan_msg.ranges = ranges
        
        self.publisher_.publish(scan_msg)

    def parse_lidar_data(self, raw_bytes):
        self.serial_buffer.extend(raw_bytes)
        
        # Process as long as we have at least one full packet
        while len(self.serial_buffer) >= 47:
            # Look for the header (0x54) and length (0x2C)
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
                    
                    # Each point is 3 bytes (2 distance, 1 intensity) starting at index 6
                    idx = 6 + i * 3
                    distance_mm = int.from_bytes(packet[idx:idx+2], byteorder='little')
                    
                    # Convert to meters
                    distance_m = distance_mm / 1000.0
                    
                    # Map to the nearest integer degree index (0-359)
                    degree_idx = int(round(point_angle)) % 360
                    self.current_ranges[degree_idx] = distance_m
                
                # Pop the successfully parsed packet from the buffer
                self.serial_buffer = self.serial_buffer[47:]
            else:
                # If sync is lost, discard 1 byte and scan for the next valid header
                self.serial_buffer.pop(0)
                
        return self.current_ranges

def main(args=None):
    rclpy.init(args=args)
    node = LidarPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.serial_port.close()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()