# Contributor: Bassel Elbahnasy
import os
import cv2
import numpy as np
import torch
import torch.nn as nn
from dotenv import load_dotenv
import tensorflow as tf
import threading
import time
from flask import Flask, Response
from flask_cors import CORS
import webbrowser
from ultralytics import YOLO
import paho.mqtt.client as mqtt
import json

# Load environment variables from a .env file if present
load_dotenv()

app = Flask(__name__)
CORS(app) # Allow CORS so the website can fetch the streams

latest_frame_tapo = None
latest_frame_pi = None

def generate_frames(camera_type):
    global latest_frame_tapo, latest_frame_pi
    while True:
        frame = None
        if camera_type == 'tapo':
            frame = latest_frame_tapo
        elif camera_type == 'pi':
            frame = latest_frame_pi
            
        if frame is None:
            time.sleep(0.01)
            continue
            
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed_tapo')
def video_feed_tapo():
    return Response(generate_frames('tapo'), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/video_feed_pi')
def video_feed_pi():
    return Response(generate_frames('pi'), mimetype='multipart/x-mixed-replace; boundary=frame')

def run_flask():
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)


def calculate_transformation_matrix(image_frame, camera_matrix, dist_coeffs, marker_length=0.10):
    """
    Detects an ArUco marker and calculates the 4x4 transformation matrix.
    marker_length is in meters (e.g., 0.10 = 10cm).
    """
    # Load the ArUco dictionary (using 4x4 dictionary for standard markers)
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    parameters = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)

    # Detect the markers in the image
    corners, ids, rejected = detector.detectMarkers(image_frame)

    transformation_matrix = None
    marker_center = None

    if ids is not None:
        # Calculate pixel center of the ArUco marker
        for i in range(len(ids)):
            if ids[i] == 0:
                marker_center = np.mean(corners[i][0], axis=0)
                break

        # Define the 3D coordinates of the marker corners in its own coordinate system
        obj_points = np.array([
            [-marker_length/2, marker_length/2, 0],
            [marker_length/2, marker_length/2, 0],
            [marker_length/2, -marker_length/2, 0],
            [-marker_length/2, -marker_length/2, 0]
        ], dtype=np.float32)

        # Iterate through detected markers (assuming ID 0 is the robot)
        for i in range(len(ids)):
            # Solve PnP to get the rotation and translation vectors
            success, rvec, tvec = cv2.solvePnP(
                obj_points, corners[i], camera_matrix, dist_coeffs, flags=cv2.SOLVEPNP_IPPE_SQUARE
            )

            if success:
                # Convert the 3x1 rotation vector (rvec) to a 3x3 rotation matrix using Rodrigues
                rotation_matrix, _ = cv2.Rodrigues(rvec)

                # Initialize a 4x4 identity matrix
                transformation_matrix = np.eye(4, dtype=np.float32)

                # Plug in the 3x3 rotation matrix
                transformation_matrix[0:3, 0:3] = rotation_matrix

                # Plug in the 3x1 translation vector (tvec)
                transformation_matrix[0:3, 3] = tvec.flatten()

                # Draw axes on the marker for visual debugging
                cv2.drawFrameAxes(image_frame, camera_matrix, dist_coeffs, rvec, tvec, 0.05)
                break # Assuming we only track one robot marker

    return transformation_matrix, image_frame, marker_center


class CameraStream:
    """
    Continually grabs frames from the camera in a background thread.
    This prevents the OpenCV buffer from filling up and causing massive delays
    when running heavy neural networks (like PyTorch and Keras).
    """
    def __init__(self, src):
        self.stream = cv2.VideoCapture(src)
        self.stream.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.grabbed, self.frame = self.stream.read()
        self.stopped = False
        
    def start(self):
        if self.stream.isOpened():
            self.thread = threading.Thread(target=self.update, args=())
            self.thread.daemon = True
            self.thread.start()
        return self

    def update(self):
        while not self.stopped:
            if not self.stream.isOpened():
                self.stopped = True
                break
            # Drains the internal buffer constantly, keeping only the most recent frame
            self.grabbed, self.frame = self.stream.read()

    def read(self):
        return self.grabbed, self.frame

    def stop(self):
        self.stopped = True
        if hasattr(self, 'thread'):
            self.thread.join()
        self.stream.release()

    def isOpened(self):
        return self.stream.isOpened()


if __name__ == '__main__':
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # 1. Load the Pre-trained YOLOv8 Fire Detection Model
    print("Loading Pretrained YOLOv8 Fire Detection model...")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    # === MODEL CONFIGURATION SELECTION ===
    # Option A: Touati Kamel (YOLOv8-Small - Higher accuracy, better for screens/indoor setups)
    # MODEL_REPO = "touati-kamel/yolov8s-forest-fire-detection"
    # MODEL_FILE = "model.pt"

    # Option B: Rabahdev (YOLOv8-Nano - Fast, but struggles with screen reflections)
    MODEL_REPO = "rabahdev/fire-smoke-yolov8n"
    MODEL_FILE = "best.pt"

    # Option C: SHOU-ISD (YOLOv8-Nano - Alternate dataset)
    # MODEL_REPO = "SHOU-ISD/fire-and-smoke"
    # MODEL_FILE = "best.pt"

    # Securely fetch model from Hugging Face cache using huggingface_hub helper
    from huggingface_hub import hf_hub_download
    try:
        print(f"Downloading custom weights from Hugging Face Hub: {MODEL_REPO}/{MODEL_FILE}...")
        model_path = hf_hub_download(repo_id=MODEL_REPO, filename=MODEL_FILE)
        model = YOLO(model_path)
        print(f"Model {MODEL_REPO} initialized successfully.")
    except Exception as e:
        print(f"Hugging Face fetch failed: {e}. Falling back to default baseline model...")
        model = YOLO("yolov8n.pt") 

    # Start Flask video streaming server in a background thread
    print("Starting Flask streaming server on port 5000...")
    print("\n" + "="*60)
    print("🌐 WEBSITE CAMERA URLs:")
    print("➔ Tapo Camera URL: http://127.0.0.1:5000/video_feed_tapo")
    print("➔ Pi Camera URL:   http://127.0.0.1:5000/video_feed_pi")
    print("="*60 + "\n")
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Automatically open the Web Command Center UI
    def open_browser():
        time.sleep(2) # Give flask time to start
        html_path = os.path.abspath(os.path.join(current_dir, "..", "Phoenix_Web_Command_Center", "index.html"))
        webbrowser.open(f"file://{html_path}")
    
    browser_thread = threading.Thread(target=open_browser)
    browser_thread.daemon = True
    browser_thread.start()

    # 1.1 Load the Keras Models for Raspberry Pi (Fire and Human)
    print("Loading Raspberry Pi Fire and Human Detection models...")
    fire_model_pi_path = os.path.join(current_dir, "Fire_Detection_Raspberry_Pi", "fire_robust_model.h5")
    human_model_pi_path = os.path.join(current_dir, "Human_Detection", "human.h5")
    
    try:
        fire_model_pi = tf.keras.models.load_model(fire_model_pi_path)
        human_model_pi = tf.keras.models.load_model(human_model_pi_path)
        print("Raspberry Pi models loaded successfully.")
    except Exception as e:
        print(f"Error loading Keras models: {e}")
        fire_model_pi, human_model_pi = None, None

    # Initialize cameras (Tapo C210 via RTSP)
    tapo_rtsp_url = os.environ.get("RTSP_URL") 
    if tapo_rtsp_url:
        cap_tapo = CameraStream(tapo_rtsp_url).start()
    else:
        print("RTSP_URL not set in .env. Falling back to the laptop webcam (0) for Tapo.")
        cap_tapo = CameraStream(0).start()

    if not cap_tapo.isOpened():
        print(f"Failed to open video stream. Input used: {tapo_rtsp_url}. Falling back to 0")
        cap_tapo = CameraStream(0).start()
        if not cap_tapo.isOpened():
            print("Failed to open fallback camera 0.")
            exit(1)

    # Initialize Raspberry Pi Camera Module 3 stream
    pi_camera_url = os.environ.get("PI_CAMERA_URL")
    if pi_camera_url:
        cap_pi = CameraStream(pi_camera_url).start()
    else:
        print("PI_CAMERA_URL not set in .env. Falling back to the laptop webcam (0) for testing the Pi models.")
        cap_pi = CameraStream(0).start()

    if not cap_pi.isOpened():
        print("Failed to open Raspberry Pi Camera stream. Falling back to 0")
        cap_pi = CameraStream(0).start()
        if not cap_pi.isOpened():
            print("Failed to open fallback camera 0 for Pi. Models will skip Pi frames.")

    # Initialize MQTT client
    mqtt_broker = os.environ.get("MQTT_BROKER", "localhost")
    print(f"Connecting to MQTT Broker at {mqtt_broker}...")
    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "Vision_Node_YOLO")
    try:
        mqtt_client.connect(mqtt_broker, 1883, 60)
        mqtt_client.loop_start()
        print("MQTT Client connected successfully.")
    except Exception as e:
        print(f"Failed to connect to MQTT broker: {e}")

    # Navigation Origin Calibration & Cooldown state
    robot_start_x = None
    robot_start_y = None
    last_heartbeat_time = 0.0
    last_goal_time = 0.0

    # Latching state for autonomous fire targeting
    latched_fire_x = None
    latched_fire_y = None
    latched_fire_active = False
    last_fire_detect_time = 0.0

    # Placeholder camera matrix
    placeholder_camera_matrix = np.array([[800, 0, 320], [0, 800, 240], [0, 0, 1]], dtype=np.float32)
    placeholder_dist_coeffs = np.zeros((4,1))

    print("Starting Robot Tracking and Fire Detection...")

    while True:
        # STEP A: Send Heartbeat (to keep robot integration watchdog happy)
        current_time = time.time()
        if current_time - last_heartbeat_time > 1.0:
            heartbeat_payload = {
                "status": "alive",
                "timestamp": current_time
            }
            try:
                mqtt_client.publish("robot/heartbeat", json.dumps(heartbeat_payload))
            except Exception:
                pass
            last_heartbeat_time = current_time

        # Get latest frames instantly
        ret_tapo, frame_tapo = cap_tapo.read()
        ret_pi, frame_pi = False, None
        
        if cap_pi.isOpened():
            ret_pi, frame_pi = cap_pi.read()
            
        if not ret_tapo or frame_tapo is None:
            time.sleep(0.01) 
            continue

        # 2. Run ArUco tracking for the robot kinematics on Tapo
        T_matrix, display_frame_tapo, marker_center = calculate_transformation_matrix(
            frame_tapo, 
            placeholder_camera_matrix, 
            placeholder_dist_coeffs, 
            marker_length=0.093
        )

        robot_x_map = 0.0
        robot_y_map = 0.0
        robot_x = None
        robot_y = None

        if T_matrix is not None:
            robot_x = T_matrix[0, 3]
            robot_y = T_matrix[1, 3]
            
            # Calibrate start position on first valid detection to align map frame
            if robot_start_x is None:
                robot_start_x = robot_x
                robot_start_y = robot_y
                print(f"[CALIBRATION] Robot origin set to camera coordinates ({robot_start_x:.3f}, {robot_start_y:.3f})")
            
            robot_x_map = robot_x - robot_start_x
            robot_y_map = robot_y - robot_start_y

        # 3. Run Pre-trained YOLOv8 Fire Detection on the SAME Tapo frame
        fire_active = False # Flag to trigger downstream MQTT pipelines
        fire_x_target = None
        fire_y_target = None
        max_conf = 0.0
        
        # Pass the frame directly to YOLOv8 with a lower threshold (0.25) for better screen sensitivity
        results = model(display_frame_tapo, conf=0.25, verbose=False, device=device.type) 

        for r in results:
            boxes = r.boxes
            for box in boxes:
                conf = float(box.conf[0])
                cls = int(box.cls[0])

                # Extract bounding box pixel coordinates
                x1, y1, x2, y2 = map(int, box.xyxy[0])

                # NEW 2D PIXEL FILTER: Ignore if it overlaps or is too close to the robot's ArUco marker in the image
                if marker_center is not None:
                    u_fire_center = (x1 + x2) / 2.0
                    v_fire_center = (y1 + y2) / 2.0
                    dist_px = np.sqrt((u_fire_center - marker_center[0])**2 + (v_fire_center - marker_center[1])**2)
                    if dist_px < 350: # 350 pixel radius around the robot's center (increased from 220)
                        continue

                # Draw a red bounding box around the validated fire/smoke target
                cv2.rectangle(display_frame_tapo, (x1, y1), (x2, y2), (0, 0, 255), 3)
                
                # Overlay label metrics
                label = f"Fire AI: {conf:.2f}"
                cv2.putText(display_frame_tapo, label, (x1, y1 - 10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

                fire_active = True
                last_fire_detect_time = current_time

                if conf > max_conf:
                    max_conf = conf
                    
                    # Calculate pixel center of the fire base (where it touches the floor)
                    u_fire = (x1 + x2) / 2.0
                    v_fire = y2
                    
                    # Pinhole projection mapping to camera coordinate space
                    z_floor = T_matrix[2, 3] if T_matrix is not None else 2.0
                    fx = placeholder_camera_matrix[0, 0]
                    fy = placeholder_camera_matrix[1, 1]
                    cx = placeholder_camera_matrix[0, 2]
                    cy = placeholder_camera_matrix[1, 2]
                    
                    x_fire_cam = ((u_fire - cx) * z_floor) / fx
                    y_fire_cam = ((v_fire - cy) * z_floor) / fy
                    
                    if robot_start_x is not None:
                        fire_x_target = x_fire_cam - robot_start_x
                        fire_y_target = y_fire_cam - robot_start_y
                    else:
                        fire_x_target = x_fire_cam - robot_x if robot_x is not None else x_fire_cam
                        fire_y_target = y_fire_cam - robot_y if robot_y is not None else y_fire_cam

                    # 3D Map-Space Filter: Ignore targets within 60cm of the starting point (0,0) or current robot position
                    dist_to_start = np.sqrt(fire_x_target**2 + fire_y_target**2)
                    dist_to_robot = 999.0
                    if robot_x_map is not None and robot_y_map is not None:
                        dist_to_robot = np.sqrt((fire_x_target - robot_x_map)**2 + (fire_y_target - robot_y_map)**2)
                    
                    if dist_to_start < 0.60 or dist_to_robot < 0.60:
                        # Skip this detection as it's on top of the robot itself
                        continue

                    # Latch target coordinate in memory
                    latched_fire_x = fire_x_target
                    latched_fire_y = fire_y_target
                    latched_fire_active = True

        # 3.2 Latch override and arrival check
        if latched_fire_active:
            # If we haven't seen any fire in the scene for 5 seconds, clear the latch
            if current_time - last_fire_detect_time > 5.0:
                print(f"[LATCH TIMEOUT] No fire detected for 5.0 seconds. Clearing latched target.")
                latched_fire_active = False
                latched_fire_x = None
                latched_fire_y = None
                fire_active = False
            else:
                # Keep the target locked and fire status active even if detector drops frames
                fire_active = True
                fire_x_target = latched_fire_x
                fire_y_target = latched_fire_y
                
                # Check if the robot has arrived at the safe stopping distance
                d_safe = 0.8  # Stop 80cm away
                dx = latched_fire_x - robot_x_map
                dy = latched_fire_y - robot_y_map
                d_total = np.sqrt(dx**2 + dy**2)
                
                # Reset latch once the robot is tracked and successfully arrives at the fire safe area
                if T_matrix is not None and d_total <= (d_safe + 0.05):
                    print(f"[LATCH CLEAR] Robot reached destination (distance: {d_total:.3f}m). Extinguishing & resetting fire target.")
                    latched_fire_active = False
                    latched_fire_x = None
                    latched_fire_y = None
                    fire_active = False

        # 3.5 Throttle MQTT messages and goal updates (every 2 seconds)
        if current_time - last_goal_time > 2.0:
            fire_payload = {
                "fire": fire_active,
                "confidence": round(max_conf if max_conf > 0.0 else 0.85, 2),
                "class": "flame" if fire_active else "none"
            }
            try:
                mqtt_client.publish("robot/fire_detected", json.dumps(fire_payload))
            except Exception as e:
                print(f"MQTT publish error (fire_detected): {e}")

            if fire_active and fire_x_target is not None and fire_y_target is not None:
                d_safe = 0.8  # Stop 80cm away from fire
                dx = fire_x_target - robot_x_map
                dy = fire_y_target - robot_y_map
                d_total = np.sqrt(dx**2 + dy**2)
                
                if d_total > d_safe:
                    x_nav = fire_x_target - (d_safe * dx / d_total)
                    y_nav = fire_y_target - (d_safe * dy / d_total)
                    
                    nav_payload = {
                        "x": round(float(x_nav), 3),
                        "y": round(float(y_nav), 3)
                    }
                    try:
                        mqtt_client.publish("ambers/robot/navigation/target", json.dumps(nav_payload))
                        print(f"[AUTONOMOUS TARGET] Fire target active! Safe Goal: x={x_nav:.3f}, y={y_nav:.3f} (Distance left: {d_total:.3f}m)")
                    except Exception as e:
                        print(f"MQTT publish error (navigation target): {e}")
                else:
                    pump_payload = {
                        "activate": True
                    }
                    try:
                        mqtt_client.publish("ambers/robot/pump", json.dumps(pump_payload))
                        print(f"[AUTONOMOUS PUMP] Robot within safe distance ({d_total:.3f}m <= {d_safe}m). Triggering extinguishing pump!")
                    except Exception as e:
                        print(f"MQTT publish error (pump): {e}")
            
            last_goal_time = current_time

        # 4. Run Raspberry Pi Fire & Human Detection (Keras) on the Pi Camera frame
        display_frame_pi = None
        if ret_pi and frame_pi is not None and fire_model_pi is not None and human_model_pi is not None:
            display_frame_pi = frame_pi.copy()
            img_size = 128
            
            # Preprocess for Fire model
            fire_pi_img = cv2.resize(frame_pi, (img_size, img_size))
            fire_pi_img = cv2.cvtColor(fire_pi_img, cv2.COLOR_BGR2RGB)
            fire_pi_img = fire_pi_img.astype(np.float32) / 255.0
            fire_pi_input = np.expand_dims(fire_pi_img, axis=0)
            
            fire_pi_pred = fire_model_pi.predict(fire_pi_input, verbose=0)[0][0]

            norm_error_x = 0.0
            norm_error_y = 0.0
            fire_localized = False

            if fire_pi_pred > 0.5:
                # 1. Isolate flame colors using HSV thresholding
                hsv = cv2.cvtColor(frame_pi, cv2.COLOR_BGR2HSV)
                lower_fire = np.array([0, 50, 50], dtype=np.uint8)     
                upper_fire = np.array([35, 255, 255], dtype=np.uint8)
                mask = cv2.inRange(hsv, lower_fire, upper_fire)
                
                # 2. Find contours to find the center of the flame
                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if contours:
                    largest_contour = max(contours, key=cv2.contourArea)
                    M = cv2.moments(largest_contour)
                    if M["m00"] != 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])
                        
                        h_pi, w_pi = frame_pi.shape[:2]
                        norm_error_x = (cx - (w_pi / 2)) / (w_pi / 2)
                        norm_error_y = (cy - (h_pi / 2)) / (h_pi / 2)
                        fire_localized = True
            
            # Preprocess for Human model
            human_pi_img = cv2.resize(frame_pi, (img_size, img_size))
            human_pi_img = cv2.cvtColor(human_pi_img, cv2.COLOR_BGR2RGB)
            human_pi_img = human_pi_img.astype(np.float32)
            human_pi_input = np.expand_dims(human_pi_img, axis=0)
            
            human_pi_pred = human_model_pi.predict(human_pi_input, verbose=0)[0][0]
            
            # Draw labels for Keras models
            font = cv2.FONT_HERSHEY_SIMPLEX
            cv2.putText(display_frame_pi, f"Pi Fire: {fire_pi_pred:.2f}", (10, 30), font, 0.8, (0, 0, 255) if fire_pi_pred > 0.5 else (0, 255, 0), 2)
            cv2.putText(display_frame_pi, f"Pi Human: {human_pi_pred:.2f}", (10, 60), font, 0.8, (255, 0, 0) if human_pi_pred > 0.5 else (0, 255, 0), 2)

        # Update global frames for Flask stream
        if display_frame_tapo is not None:
            ret, buffer = cv2.imencode('.jpg', display_frame_tapo)
            if ret:
                latest_frame_tapo = buffer.tobytes()
        if display_frame_pi is not None:
            ret, buffer = cv2.imencode('.jpg', display_frame_pi)
            if ret:
                latest_frame_pi = buffer.tobytes()

        # --- Display the Windows ---
        cv2.namedWindow('Vision Node: Tapo Tracking & AI', cv2.WINDOW_NORMAL)
        cv2.resizeWindow('Vision Node: Tapo Tracking & AI', 1280, 720)
        cv2.imshow('Vision Node: Tapo Tracking & AI', display_frame_tapo)
        
        if display_frame_pi is not None:
            cv2.namedWindow('Vision Node: Pi Camera AI', cv2.WINDOW_NORMAL)
            cv2.resizeWindow('Vision Node: Pi Camera AI', 640, 480)
            cv2.imshow('Vision Node: Pi Camera AI', display_frame_pi)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap_tapo.stop()
    if cap_pi.isOpened():
        cap_pi.stop()
    cv2.destroyAllWindows()