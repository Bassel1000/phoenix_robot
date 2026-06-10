# Contributors: Bassel Elbahnasy
# Optimized according to the Phoenix Robot Wiring & GPIO Reference Table
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json
from gpiozero import ContinuousServo, Servo, OutputDevice
from gpiozero.pins.pigpio import PiGPIOFactory
import time

class NozzleTrackingController(Node):
    def __init__(self):
        super().__init__('nozzle_tracking_controller')
        self.get_logger().info("Initializing Phoenix Servo Nozzle Tracking Node with HW PWM...")
        
        # --- Hardware Factory Configuration ---
        # Using pigpio pin factory to natively leverage the hardware PWM clocks 
        # specified for GPIO 18 and 13 in image_736bcb.png
        try:
            self.pin_factory = PiGPIOFactory()
        except IOError:
            self.get_logger().warn("pigpio daemon not running! Falling back to software PWM.")
            self.pin_factory = None
        
        # --- Actuator Allocation from image_736bcb.png ---
        # 360° Continuous Servo for Horizontal Panning (Yaw) -> GPIO 18 (HW PWM0)
        self.pan_servo = ContinuousServo(18, initial_value=0.0, pin_factory=self.pin_factory) 
        
        # 180° Standard Servo for Vertical Tilting (Pitch) -> GPIO 13 (HW PWM1)
        # Pulse width window calibrated to standard 1000μs - 2000μs limits from the reference sheet
        self.tilt_servo = Servo(
            13, 
            initial_value=0.0, 
            min_pulse_width=1/1000, 
            max_pulse_width=2/1000, 
            pin_factory=self.pin_factory
        ) 
        
        # 24V Water Pump Relay -> GPIO 26 (PUMP_CONTROL)
        self.pump_relay = OutputDevice(26, active_high=True, initial_value=False)
        
        # --- Tracking Bounds and Deadzones ---
        self.current_tilt = 0.0  # Positional baseline (ranges from -1.0 to 1.0)
        self.deadzone = 0.12     # Precision centering threshold to prevent servo hunting
        
        # Subscription to incoming global/local localized fire data payload
        self.subscription = self.create_subscription(
            String, 
            'mqtt_fire_alerts', 
            self.fire_tracking_callback, 
            10
        )

    def fire_tracking_callback(self, msg):
        try:
            payload = json.loads(msg.data)
            
            # Failsafe: Shut down all tracking and water pressure if no active flame detected
            if not payload.get("active", False):
                self.pan_servo.value = 0.0 
                self.pump_relay.off()
                return

            error_x = payload.get("error_x", 0.0)
            error_y = payload.get("error_y", 0.0)

            # --- 1. PAN CONTROL (360° Continuous Servo on GPIO 18) ---
            if abs(error_x) > self.deadzone:
                # Proportional velocity assignment. Speed steps scale down as target approaches center
                # Clamped tightly at +/- 0.35 to prevent severe physical nozzle whipping
                velocity = error_x * 0.4 
                self.pan_servo.value = max(-0.35, min(0.35, velocity))
            else:
                self.pan_servo.value = 0.0  # Target horizontally aligned. Hard brake velocity loop.

            # --- 2. TILT CONTROL (180° Positional Servo on GPIO 13) ---
            if abs(error_y) > self.deadzone:
                # Incremental positional correction step
                self.current_tilt -= error_y * 0.04 
                self.current_tilt = max(-1.0, min(1.0, self.current_tilt)) # Enforce mechanical travel stops
                self.tilt_servo.value = self.current_tilt

            # --- 3. AUTOMATIC SUPPRESSION ENGAGEMENT ---
            # If the flame centroid is trapped directly within the deadzone box on both coordinates:
            if abs(error_x) <= self.deadzone and abs(error_y) <= self.deadzone:
                self.get_logger().info("🎯 TARGET LOCKED: Dispensing suppression payload.")
                self.pump_relay.on()
            else:
                # Kill pump instantly if targeting drifts out of safety limits
                self.pump_relay.off()

        except Exception as e:
            self.get_logger().error(f"Error executing tracking callback: {e}")

def main(args=None):
    rclpy.init(args=args)
    node = NozzleTrackingController()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        # Emergency hardware safety line clearing
        node.pan_servo.value = 0.0
        node.pump_relay.off()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()