# Contributors: Bassel Elbahnasy
# Optimized according to the Phoenix Robot Wiring & GPIO Reference Table
import rclpy
from rclpy.node import Node
from gpiozero import Servo
from gpiozero.pins.pigpio import PiGPIOFactory
import paho.mqtt.client as mqtt

class NozzleController(Node):
    def __init__(self):
        super().__init__('nozzle_controller')
        self.get_logger().info("Initializing Phoenix Nozzle Controller (Manual Mode)...")
        
        # --- Hardware Factory Configuration ---
        try:
            self.pin_factory = PiGPIOFactory()
        except Exception:
            self.get_logger().warn("pigpio daemon not running! Falling back to software PWM.")
            self.pin_factory = None
        
        # --- Actuator Allocation ---
        # 360° Continuous Servo for Horizontal Panning (Yaw) -> GPIO 19
        # Use Servo instead, set min/max pulse widths for continuous rotation
        try:
            # Try ContinuousServo first. Start detached so the nozzle does not move on boot.
            from gpiozero import ContinuousServo
            self.pan_servo = ContinuousServo(19, initial_value=None, pin_factory=self.pin_factory)
            self.use_continuous = True
        except ImportError:
            # Fall back to Servo for compatibility
            self.get_logger().warn("ContinuousServo not available, using Servo fallback for pan.")
            self.pan_servo = Servo(
                19, 
                initial_value=None, 
                min_pulse_width=0.0005, 
                max_pulse_width=0.0025,
                pin_factory=self.pin_factory
            )
            self.use_continuous = False
        
        # 180° Standard Servo for Vertical Tilting (Pitch) -> GPIO 13
        self.tilt_servo = Servo(
            13, 
            initial_value=None, 
            min_pulse_width=0.0005, 
            max_pulse_width=0.0025, 
            pin_factory=self.pin_factory
        )
        
        # --- State ---
        self.current_tilt = 0.0
        self.tilt_direction = 0.0  # -1 for down, 1 for up, 0 for stop
        self.pan_command = "STOP"  # Store pan command for thread-safety
        self.pan_speed = 0.3
        self.tilt_speed = 0.02     # Smooth interpolation step per tick

        # Keep both servos idle until the first command arrives.
        self.release_servos()
        self.pan_is_detached = True
        self.tilt_is_detached = True
        
        # 20Hz Control Loop for Smooth Tilting
        self.timer = self.create_timer(0.05, self.control_loop)
        
        # --- MQTT Client Setup (Supports both paho-mqtt v1.x and v2.x) ---
        try:
            self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="Nozzle_Controller")
        except AttributeError:
            self.mqtt_client = mqtt.Client(client_id="Nozzle_Controller")
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_message = self.on_mqtt_message
        
        import os
        broker_ip = os.environ.get('MQTT_BROKER_IP', 'localhost')
        try:
            self.mqtt_client.connect(broker_ip, 1883, 60)
            self.mqtt_client.loop_start()
            self.get_logger().info("MQTT client connected for nozzle control.")
        except Exception as e:
            self.get_logger().error(f"Failed to connect to MQTT broker: {e}")

    def on_mqtt_connect(self, client, userdata, flags, rc, properties):
        self.get_logger().info("MQTT connected, subscribing to nozzle commands...")
        client.subscribe("phoenix/cmd/nozzle")

    def on_mqtt_message(self, client, userdata, msg):
        command = msg.payload.decode().strip().upper()
        self.get_logger().info(f"Received nozzle command: {command}")
        
        # We only update state variables here to ensure thread-safety.
        # The actual servo manipulation is done in the control_loop (ROS timer thread).
        if command == "LEFT" or command == "RIGHT":
            self.pan_command = command
        elif command == "UP":
            self.tilt_direction = 1.0
            self.pan_command = "STOP"
        elif command == "DOWN":
            self.tilt_direction = -1.0
            self.pan_command = "STOP"
        elif command == "STOP":
            self.tilt_direction = 0.0
            self.pan_command = "STOP"
        elif command == "CENTER":
            self.tilt_direction = 0.0
            self.pan_command = "CENTER"

    def control_loop(self):
        # Handle Tilt
        if self.tilt_direction != 0.0:
            new_tilt = self.current_tilt + self.tilt_direction * self.tilt_speed
            new_tilt = max(-1.0, min(1.0, new_tilt))
            if new_tilt != self.current_tilt or self.tilt_is_detached:
                self.current_tilt = new_tilt
                self.tilt_servo.value = self.current_tilt
                self.tilt_is_detached = False
        else:
            if not self.tilt_is_detached:
                self.tilt_servo.detach()
                self.tilt_is_detached = True

        # Handle Pan
        if self.pan_command == "LEFT":
            self.pan_servo.value = -self.pan_speed
            self.pan_is_detached = False
        elif self.pan_command == "RIGHT":
            self.pan_servo.value = self.pan_speed
            self.pan_is_detached = False
        elif self.pan_command == "CENTER":
            self.current_tilt = 0.0
            self.tilt_servo.value = 0.0
            self.tilt_is_detached = False
            self.pan_command = "STOP" # Center only triggers once
        elif self.pan_command == "STOP":
            if not self.pan_is_detached:
                if self.use_continuous:
                    self.pan_servo.value = 0.0
                else:
                    self.pan_servo.detach()
                self.pan_is_detached = True

    def release_servos(self):
        self.pan_servo.detach()
        self.tilt_servo.detach()

def main(args=None):
    rclpy.init(args=args)
    node = NozzleController()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.release_servos()
        node.mqtt_client.loop_stop()
        node.mqtt_client.disconnect()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()
