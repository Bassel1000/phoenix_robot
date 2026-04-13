import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool
from gpiozero import OutputDevice
import time

class PumpController(Node):
    def __init__(self):
        super().__init__('pump_controller')
        self.get_logger().info("Initializing Phoenix Pump Controller...")
        
        # The relay for the 24V pump is connected to GPIO 26 
        self.pump_relay = OutputDevice(26, active_high=True, initial_value=False)
        
        # Subscribe to a topic that signals when the Nav2 goal is reached
        self.subscription = self.create_subscription(
            Bool, 
            'target_reached', 
            self.target_reached_callback, 
            10
        )

    def target_reached_callback(self, msg):
        if msg.data:
            self.get_logger().info("Target reached! Activating 24V water pump...")
            self.activate_pump(duration=5.0) # Spray for 5 seconds
            
    def activate_pump(self, duration):
        self.pump_relay.on()
        time.sleep(duration)
        self.pump_relay.off()
        self.get_logger().info("Pump deactivated.")

def main(args=None):
    rclpy.init(args=args)
    node = PumpController()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.pump_relay.off() # Ensure pump is off on shutdown
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()