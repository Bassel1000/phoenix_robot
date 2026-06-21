# Contributor: Bassel Elbahnasy
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, TransformStamped
from nav_msgs.msg import Odometry
from tf2_ros import TransformBroadcaster
from gpiozero import PWMOutputDevice
import math

class MotorController(Node):
    def __init__(self):
        super().__init__('motor_controller')
        self.get_logger().info("Initializing Phoenix Motor Controller...")

        # ------- MOTOR HARDWARE CONFIGURATION -------
        # If your robot spins when you tell it to go straight, or goes the wrong way, 
        # change these Booleans to True/False until it drives perfectly.
        self.swap_left_and_right = False 
        self.invert_left         = True   
        self.invert_right        = False  
        # --------------------------------------------
        
        # Left Motor Driver (BTS7960)
        self.left_fwd = PWMOutputDevice(17)
        self.left_rev = PWMOutputDevice(27)
        
        # Right Motor Driver (BTS7960)
        self.right_fwd = PWMOutputDevice(25)
        self.right_rev = PWMOutputDevice(23)
        
        # Acceleration / Smoothing Configuration
        # 'step' is how much the speed can change every 0.05 seconds (the timer rate).
        # We increase this to prevent double-smoothing (since Nav2 already smooths velocity).
        self.linear_step = 0.2 
        self.angular_step = 0.5
        
        self.target_linear = 0.0
        self.current_linear = 0.0
        self.target_angular = 0.0
        self.current_angular = 0.0
        self.last_cmd_time = self.get_clock().now()
        
        # Open-loop Odometry setup
        self.odom_pub = self.create_publisher(Odometry, 'odom', 10)
        self.tf_broadcaster = TransformBroadcaster(self)
        self.odom_x = 0.0
        self.odom_y = 0.0
        self.odom_yaw = 0.0
        
        self.subscription = self.create_subscription(Twist, 'cmd_vel', self.cmd_vel_callback, 10)
        self.timer = self.create_timer(0.05, self.control_loop) # 20Hz control loop
            
    def approach_target(self, current, target, step):
        if current < target:
            return min(current + step, target)
        elif current > target:
            return max(current - step, target)
        return target

    def set_motor(self, fwd_pin, rev_pin, speed):
        # Cap at 95% PWM (0.95) instead of 100% (1.0). 
        # High-power BTS7960 motor drivers use bootstrap capacitors for their MOSFETs. 
        # If driven at exactly 100% duty cycle, the capacitor discharges and the motor stalls/whines!
        speed = max(min(speed, 0.95), -0.95) 
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
        # Update targets based on joystick/keyboard input
        self.target_linear = msg.linear.x
        self.target_angular = msg.angular.z
        self.last_cmd_time = self.get_clock().now()

    def control_loop(self):
        # --- SAFETY WATCHDOG ---
        # If no cmd_vel received in the last 0.5 seconds, auto-stop!
        # This prevents the robot from crashing if Nav2 loses odometry or connection drops.
        if (self.get_clock().now() - self.last_cmd_time).nanoseconds > 5e8: # 0.5 seconds in ns
            self.target_linear = 0.0
            self.target_angular = 0.0

        # Smoothly interpolate current speeds towards target speeds
        self.current_linear = self.approach_target(self.current_linear, self.target_linear, self.linear_step)
        self.current_angular = self.approach_target(self.current_angular, self.target_angular, self.angular_step)
        
        # Integrate Odometry
        dt = 0.05
        self.odom_yaw += self.current_angular * dt
        self.odom_x += self.current_linear * math.cos(self.odom_yaw) * dt
        self.odom_y += self.current_linear * math.sin(self.odom_yaw) * dt
        
        # Publish TF
        t = TransformStamped()
        t.header.stamp = self.get_clock().now().to_msg()
        t.header.frame_id = 'odom'
        t.child_frame_id = 'base_footprint'
        t.transform.translation.x = self.odom_x
        t.transform.translation.y = self.odom_y
        t.transform.translation.z = 0.0
        t.transform.rotation.z = math.sin(self.odom_yaw / 2.0)
        t.transform.rotation.w = math.cos(self.odom_yaw / 2.0)
        self.tf_broadcaster.sendTransform(t)
        
        # Publish Odometry Topic for Nav2 Velocity Feedback
        odom = Odometry()
        odom.header.stamp = t.header.stamp
        odom.header.frame_id = 'odom'
        odom.child_frame_id = 'base_footprint'
        odom.pose.pose.position.x = self.odom_x
        odom.pose.pose.position.y = self.odom_y
        odom.pose.pose.orientation = t.transform.rotation
        odom.twist.twist.linear.x = self.current_linear
        odom.twist.twist.angular.z = self.current_angular
        self.odom_pub.publish(odom)
        
        # Implement true inverse kinematics from Section 10.2
        B = 0.35   # Track Width
        V_max = 1.0 # Base scaling factor

        # Skid-steer robots require huge torque to overcome lateral wheel friction when turning.
        # We amplify the angular command specifically to break static friction.
        skid_steer_turn_boost = 5.0 

        v_l = self.current_linear - (self.current_angular * B / 2.0 * skid_steer_turn_boost)
        v_r = self.current_linear + (self.current_angular * B / 2.0 * skid_steer_turn_boost)

        # Convert target velocities to normalized percentage
        left_speed = v_l / V_max
        right_speed = v_r / V_max
        
        # --- DEADBAND COMPENSATOR ---
        # The heavy robot stalls below ~65% PWM but rockets too fast at 95% PWM.
        # This maps any requested movement into the "usable" power band.
        def apply_deadband(spd, deadband=0.65):
            if abs(spd) < 0.05: return 0.0
            sign = 1.0 if spd > 0 else -1.0
            # Scale the speed into the active range
            return sign * (deadband + abs(spd) * (0.95 - deadband))
            
        left_speed = apply_deadband(left_speed)
        right_speed = apply_deadband(right_speed)
        
        # Apply hardware fixes if the physical wiring is swapped/reversed
        if self.swap_left_and_right:
            left_speed, right_speed = right_speed, left_speed
        if self.invert_left:
            left_speed = -left_speed
        if self.invert_right:
            right_speed = -right_speed
            
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