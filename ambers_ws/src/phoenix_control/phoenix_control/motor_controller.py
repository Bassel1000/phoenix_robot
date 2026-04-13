import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from gpiozero import PWMOutputDevice

class MotorController(Node):
    def __init__(self):
        super().__init__('motor_controller')
        self.get_logger().info("Initializing Phoenix Motor Controller...")

        # Left Motor Driver (BTS7960)
        self.left_fwd = PWMOutputDevice(17)
        self.left_rev = PWMOutputDevice(27)
        
        # Right Motor Driver (BTS7960)
        self.right_fwd = PWMOutputDevice(22)
        self.right_rev = PWMOutputDevice(23)
        
        self.subscription = self.create_subscription(Twist, 'cmd_vel', self.cmd_vel_callback, 10)
            
    def set_motor(self, fwd_pin, rev_pin, speed):
        speed = max(min(speed, 1.0), -1.0) 
        if speed > 0:
            fwd_pin.value = speed
            rev_pin.value = 0.0
        elif speed < 0:
            fwd_pin.value = 0.0
            rev_pin.value = -speed 
        else:
            fwd_pin.value = 0.0
            rev_pin.value = 0.0

    def cmd_vel_callback(self, msg):
        linear = msg.linear.x
        angular = msg.angular.z
        
        left_speed = linear - angular
        right_speed = linear + angular
        
        max_speed = max(abs(left_speed), abs(right_speed))
        if max_speed > 1.0:
            left_speed /= max_speed
            right_speed /= max_speed
            
        self.set_motor(self.left_fwd, self.left_rev, left_speed)
        self.set_motor(self.right_fwd, self.right_rev, right_speed)

def main(args=None):
    rclpy.init(args=args)
    node = MotorController()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.set_motor(node.left_fwd, node.left_rev, 0.0)
        node.set_motor(node.right_fwd, node.right_rev, 0.0)
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()