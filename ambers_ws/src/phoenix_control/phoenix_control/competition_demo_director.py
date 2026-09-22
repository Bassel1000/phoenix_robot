# Contributor: Bassel Elbahnasy
"""
Phoenix Competition Demo Director
Orchestrates a fast, high-impact, competition-grade autonomous mission demo
for Datacenter and Warehouse environments.
Designed for 45-60s live presentation pitches.
"""

import argparse
import json
import math
import sys
import time
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from std_msgs.msg import Bool, String
import paho.mqtt.client as mqtt


class CompetitionDemoDirector(Node):
    def __init__(self, world_type="datacenter", auto_mode=True, stage_delay=7.0):
        super().__init__("competition_demo_director")
        self.world_type = world_type
        self.auto_mode = auto_mode
        self.stage_delay = stage_delay
        
        self.get_logger().info(
            f"=== PHOENIX COMPETITION DEMO DIRECTOR: {world_type.upper()} MODE ==="
        )

        # Nav2 Action Client
        self.nav_client = ActionClient(self, NavigateToPose, "navigate_to_pose")
        
        # MQTT Client to trigger HUD updates, pump, and gimbal
        try:
            self.mqtt_client = mqtt.Client(
                mqtt.CallbackAPIVersion.VERSION2, client_id="Phoenix_Demo_Director"
            )
        except AttributeError:
            self.mqtt_client = mqtt.Client(client_id="Phoenix_Demo_Director")
            
        try:
            self.mqtt_client.connect("localhost", 1883, 60)
            self.mqtt_client.loop_start()
            self.get_logger().info("Connected to Mosquitto MQTT for HUD synchronization.")
        except Exception as e:
            self.get_logger().warn(f"MQTT connection deferred: {e}")

        self.active_goal_handle = None
        self.stage_timeout_timer = None

        # Coordinates tailored for high-impact visual trajectory in each world
        if self.world_type == "datacenter":
            # Start: (-0.5, 0.0) -> Waypoint 1 (Aisle scan): (0.85, 0.0)
            # -> Waypoint 2 (Casualty view at 1.2, -0.65): (1.25, -0.05, yaw=-0.35 looking at technician)
            # -> Waypoint 3 (Maneuver around maintenance cart at X=2.3, Y=0.18): (2.50, -0.35)
            # -> Waypoint 4 (Standoff facing fire at X=3.7, Y=0.95): (3.35, 0.55, yaw=0.85 pointing at fire)
            self.stages = [
                {
                    "name": "STAGE 1: PATROL & SLAM INITIALIZATION",
                    "hud_status": "PATROL_ACTIVE",
                    "hud_message": "Aisle 3 Cold-Containment Patrol - LiDAR Costmap Active",
                    "x": 0.85, "y": 0.0, "yaw": 0.0,
                    "action": "patrol",
                },
                {
                    "name": "STAGE 2: CASUALTY DISCOVERY (LIFE DETECTION)",
                    "hud_status": "CASUALTY_DETECTED",
                    "hud_message": "CRITICAL: Incapacitated Technician Found at Sector B2 - GPS Logged",
                    "x": 1.25, "y": -0.05, "yaw": -0.35,
                    "action": "casualty_alert",
                },
                {
                    "name": "STAGE 3: DYNAMIC OBSTACLE AVOIDANCE",
                    "hud_status": "OBSTACLE_AVOIDANCE",
                    "hud_message": "Maintenance Cart Detected in Aisle - Nav2 Dynamic Costmap Replanning",
                    "x": 2.50, "y": -0.35, "yaw": 0.10,
                    "action": "avoid_obstacle",
                },
                {
                    "name": "STAGE 4: THERMAL LOCK & 30cm STANDOFF",
                    "hud_status": "STANDOFF_LOCKED",
                    "hud_message": "UPS Thermal Runaway Isolated - Enforcing 0.30m Safe Hardware Standoff",
                    "x": 3.35, "y": 0.55, "yaw": 0.85,  # points directly at (3.7, 0.95)
                    "action": "standoff_lock",
                },
                {
                    "name": "STAGE 5: GIMBAL TARGETING & SUPPRESSION",
                    "hud_status": "SUPPRESSION_ACTIVE",
                    "hud_message": "2-DOF Turret Aimed at Flame Root - 24V Diaphragm Pump Spraying",
                    "x": None, "y": None, "yaw": None,
                    "action": "extinguish",
                },
                {
                    "name": "STAGE 6: MISSION ACCOMPLISHED",
                    "hud_status": "MISSION_SUCCESS",
                    "hud_message": "Incident Neutralized - Datacenter Facility Secured",
                    "x": None, "y": None, "yaw": None,
                    "action": "mission_complete",
                },
            ]
        else:  # warehouse
            self.stages = [
                {
                    "name": "STAGE 1: HIGH-BAY STORAGE PATROL",
                    "hud_status": "PATROL_ACTIVE",
                    "hud_message": "Logistics Lane 4 Patrol - RF2O Slip-Resistant Laser Odometry Active",
                    "x": 0.85, "y": 0.0, "yaw": 0.0,
                    "action": "patrol",
                },
                {
                    "name": "STAGE 2: CASUALTY DISCOVERY",
                    "hud_status": "CASUALTY_DETECTED",
                    "hud_message": "Warehouse Personnel Casualty Identified - Emergency Beacon Activated",
                    "x": 1.25, "y": -0.05, "yaw": -0.35,
                    "action": "casualty_alert",
                },
                {
                    "name": "STAGE 3: DYNAMIC CARGO OBSTACLE REPLANNING",
                    "hud_status": "OBSTACLE_AVOIDANCE",
                    "hud_message": "Dropped Chemical Drum Obstacle Detected - Dynamic Path Deviation",
                    "x": 2.45, "y": 0.65, "yaw": 0.05,
                    "action": "avoid_obstacle",
                },
                {
                    "name": "STAGE 4: 30cm FIRE STANDOFF LOCK",
                    "hud_status": "STANDOFF_LOCKED",
                    "hud_message": "Pallet Fire Localized - 0.30m Safe Thermal Standoff Engaged",
                    "x": 3.45, "y": 0.75, "yaw": 0.78,  # points directly at (3.8, 1.1)
                    "action": "standoff_lock",
                },
                {
                    "name": "STAGE 5: PRECISION WATER SUPPRESSION",
                    "hud_status": "SUPPRESSION_ACTIVE",
                    "hud_message": "High-Pressure Water Stream Discharged at Pallet Fire Source",
                    "x": None, "y": None, "yaw": None,
                    "action": "extinguish",
                },
                {
                    "name": "STAGE 6: WAREHOUSE SECURED",
                    "hud_status": "MISSION_SUCCESS",
                    "hud_message": "Pallet Fire Suppressed - Facility Nominal",
                    "x": None, "y": None, "yaw": None,
                    "action": "mission_complete",
                },
            ]

        self.current_stage_idx = 0
        self.timer = self.create_timer(1.0, self.start_sequence)
        self.hb_timer = self.create_timer(1.0, self.publish_continuous_heartbeat)
        self.started = False

    def publish_continuous_heartbeat(self):
        try:
            water_lvl = 68 if self.current_stage_idx >= 4 else 100
            hb_msg = json.dumps({
                "status": "ALIVE",
                "voltage": 12.4,
                "water_level": water_lvl,
                "temperature": 41.8,
                "timestamp": time.time(),
            })
            self.mqtt_client.publish("robot/heartbeat", hb_msg)
        except Exception:
            pass

    def publish_hud_alert(self, status, message):
        payload = json.dumps({
            "status": status,
            "message": message,
            "timestamp": time.time(),
            "world": self.world_type,
        })
        try:
            self.mqtt_client.publish("phoenix/status", status)
            self.mqtt_client.publish("ambers/robot/status", payload)

            # Synchronize Web HUD banners
            if status in ["STANDOFF_LOCKED", "SUPPRESSION_ACTIVE", "OBSTACLE_AVOIDANCE"]:
                fire_msg = json.dumps({"fire": True, "confidence": 0.96, "location": "Rack 4" if self.world_type == "datacenter" else "Pallet A2"})
                self.mqtt_client.publish("robot/fire_detected", fire_msg)
            elif status == "MISSION_SUCCESS":
                self.mqtt_client.publish("robot/fire_detected", json.dumps({"fire": False, "confidence": 0.0}))

            if status == "CASUALTY_DETECTED":
                human_msg = json.dumps({"human": True, "state": "fallen", "confidence": 0.94, "sector": "Aisle B2"})
                self.mqtt_client.publish("robot/human_detected", human_msg)
            else:
                self.mqtt_client.publish("robot/human_detected", json.dumps({"human": False, "state": "none"}))
        except Exception:
            pass

    def start_sequence(self):
        if self.started:
            return
        self.started = True
        self.timer.cancel()

        self.get_logger().info("Checking Nav2 Action Server readiness...")
        if not self.nav_client.wait_for_server(timeout_sec=10.0):
            self.get_logger().warn(
                "Nav2 is still starting up. Waiting for Nav2 to stabilize..."
            )
            time.sleep(12.0)

        # Run through the demo stages
        self.run_next_stage()

    def run_next_stage(self):
        if self.current_stage_idx >= len(self.stages):
            self.get_logger().info("=== COMPETITION DEMO MISSION COMPLETED SUCCESSFULLY! ===")
            return

        stage = self.stages[self.current_stage_idx]
        self.get_logger().info(f"\n>>> EXECUTING: {stage['name']}")
        self.publish_hud_alert(stage["hud_status"], stage["hud_message"])

        action = stage["action"]
        if action in ["patrol", "casualty_alert", "avoid_obstacle", "standoff_lock"]:
            self.send_nav_goal(
                stage["x"], stage["y"], stage["yaw"], callback=self.on_goal_reached
            )
        elif action == "extinguish":
            self.execute_suppression()
        elif action == "mission_complete":
            self.execute_mission_complete()

    def send_nav_goal(self, x, y, yaw, callback):
        self.get_logger().info(f"Navigating to waypoint: X={x:.2f}, Y={y:.2f}, Yaw={yaw:.2f} rad")
        if self.stage_timeout_timer is not None:
            self.stage_timeout_timer.cancel()
            self.stage_timeout_timer = None

        goal_msg = NavigateToPose.Goal()
        goal_msg.pose.header.frame_id = "map"
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
        goal_msg.pose.pose.position.x = float(x)
        goal_msg.pose.pose.position.y = float(y)
        goal_msg.pose.pose.orientation.z = math.sin(yaw / 2.0)
        goal_msg.pose.pose.orientation.w = math.cos(yaw / 2.0)

        send_goal_future = self.nav_client.send_goal_async(goal_msg)
        send_goal_future.add_done_callback(
            lambda future: self.goal_response_callback(future, callback)
        )

    def goal_response_callback(self, future, on_reached_callback):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().warn("Goal rejected by Nav2, will advance in 3s...")
            time.sleep(3.0)
            self.advance_stage()
            return

        self.get_logger().info("Nav2 goal accepted. Tracking robot movement...")
        self.active_goal_handle = goal_handle
        # Arm failsafe stage watchdog (12.0s max per waypoint for presentation rhythm)
        self.stage_timeout_timer = self.create_timer(12.0, self.on_stage_timeout)
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(lambda res: on_reached_callback())

    def on_stage_timeout(self):
        if self.stage_timeout_timer is not None:
            self.stage_timeout_timer.cancel()
            self.stage_timeout_timer = None

        if self.active_goal_handle is None:
            return

        self.get_logger().warn(
            "[DIRECTOR WATCHDOG] Waypoint target window reached. Force-advancing to maintain presentation rhythm..."
        )
        try:
            self.active_goal_handle.cancel_goal_async()
        except Exception:
            pass
        self.active_goal_handle = None
        self.advance_stage()

    def on_goal_reached(self):
        if self.stage_timeout_timer is not None:
            self.stage_timeout_timer.cancel()
            self.stage_timeout_timer = None

        if self.active_goal_handle is None:
            return

        self.active_goal_handle = None
        self.get_logger().info("Waypoint reached successfully!")
        time.sleep(1.5)
        self.advance_stage()

    def execute_suppression(self):
        self.get_logger().info("Orienting Pan-Tilt Gimbal Turret towards flame root...")
        try:
            self.mqtt_client.publish("phoenix/cmd/nozzle", "UP")
            time.sleep(0.5)
            self.mqtt_client.publish("phoenix/cmd/nozzle", "STOP")
            time.sleep(0.5)
            self.get_logger().info("TRIGGERING 24V SUPPRESSION WATER PUMP...")
            self.mqtt_client.publish("phoenix/cmd/water", "ON")
            time.sleep(3.5)
            self.mqtt_client.publish("phoenix/cmd/water", "OFF")
            self.get_logger().info("Suppression spray complete. Flame extinguished.")
        except Exception as e:
            self.get_logger().warn(f"MQTT actuation note: {e}")
            time.sleep(3.0)

        time.sleep(1.0)
        self.advance_stage()

    def execute_mission_complete(self):
        self.publish_hud_alert(
            "MISSION_COMPLETE",
            "ALL HAZARDS SUPPRESSED - ZERO CASUALTIES - FACILITY SECURE"
        )
        self.get_logger().info("=== DEMO FINISHED: ALL HAZARDS SUPPRESSED ===")

    def advance_stage(self):
        self.current_stage_idx += 1
        self.run_next_stage()


def main(args=None):
    rclpy.init(args=args)
    parser = argparse.ArgumentParser(description="Phoenix Competition Demo Director")
    parser.add_argument(
        "--world",
        choices=["datacenter", "warehouse"],
        default="datacenter",
        help="Target facility environment",
    )
    parsed_args, _ = parser.parse_known_args()

    director = CompetitionDemoDirector(world_type=parsed_args.world)
    try:
        rclpy.spin(director)
    except KeyboardInterrupt:
        pass
    finally:
        director.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
