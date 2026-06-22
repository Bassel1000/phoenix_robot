# Contributor: Bassel Elbahnasy
import os
import cv2
import numpy as np
import torch
import torch.nn as nn
from dotenv import load_dotenv

# Fix for Keras 3 BatchNormalization deserialization error with older .h5 models
os.environ["TF_USE_LEGACY_KERAS"] = "1"
import tensorflow as tf
import threading
import time
from flask import Flask, Response
from flask_cors import CORS
import webbrowser
from ultralytics import YOLO
import paho.mqtt.client as mqtt
import json
import math
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
        valid_robot_ids = [1, 2, 3,4]
        flat_ids = ids.flatten()
        # Calculate pixel center of the ArUco marker
        for i in range(len(flat_ids)):
            if flat_ids[i] in valid_robot_ids:
                marker_center = np.mean(corners[i][0], axis=0)
                break

        # Define the 3D coordinates of the marker corners in its own coordinate system
        obj_points = np.array([
            [-marker_length/2, marker_length/2, 0],
            [marker_length/2, marker_length/2, 0],
            [marker_length/2, -marker_length/2, 0],
            [-marker_length/2, -marker_length/2, 0]
        ], dtype=np.float32)

        # Iterate through detected markers
        for i in range(len(flat_ids)):
            if flat_ids[i] not in valid_robot_ids:
                continue
                
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
                break # We only need to track one valid robot marker at a time

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


class TCPCameraStream:
    """
    Continually grabs raw MJPEG frames from a TCP socket (e.g. from rpicam-vid --listen).
    OpenCV's VideoCapture often hangs on raw TCP streams without HTTP boundaries.
    """
    def __init__(self, src):
        import urllib.parse
        import socket
        parsed = urllib.parse.urlparse(src)
        self.host = parsed.hostname
        self.port = parsed.port
        self.stopped = False
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(5.0)
        self.frame = None
        self.grabbed = False
        try:
            self.sock.connect((self.host, self.port))
            # Put socket back in blocking mode for the reading loop, or keep timeout
            self.sock.settimeout(2.0)
            self._is_opened = True
        except Exception as e:
            print(f"TCPCameraStream failed to connect to {src}: {e}")
            self._is_opened = False
            self.sock = None

    def start(self):
        if self._is_opened:
            self.thread = threading.Thread(target=self.update, args=())
            self.thread.daemon = True
            self.thread.start()
        return self

    def update(self):
        import numpy as np
        stream_bytes = b''
        while not self.stopped and self._is_opened:
            try:
                data = self.sock.recv(65536)
                if not data:
                    print("TCPCameraStream: Connection closed by server.")
                    break
                stream_bytes += data
                # Look for JPEG Start of Image (FF D8) and End of Image (FF D9)
                a = stream_bytes.rfind(b'\xff\xd8')
                b = stream_bytes.rfind(b'\xff\xd9')
                if a != -1 and b != -1 and b > a:
                    jpg = stream_bytes[a:b+2]
                    # Keep only the tail end to avoid memory leaks
                    stream_bytes = stream_bytes[b+2:]
                    frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                    if frame is not None:
                        self.frame = frame
                        self.grabbed = True
            except Exception as e:
                # Timeout is normal if no frames arrive instantly, just keep trying
                if "timed out" not in str(e).lower():
                    print(f"TCPCameraStream read error: {e}")
                    break
        self._is_opened = False
        if self.sock:
            self.sock.close()

    def read(self):
        return self.grabbed, self.frame

    def stop(self):
        self.stopped = True
        if hasattr(self, 'thread'):
            self.thread.join(timeout=1.0)
        if self.sock:
            self.sock.close()

    def isOpened(self):
        return self._is_opened


class FireDetectionModel(nn.Module):
    def __init__(self, S=7, C=2):
        super().__init__()
        self.S = S
        self.C = C

        self.backbone = nn.Sequential(
            nn.Conv2d(3, 16, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(16, 32, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(64, 128, 3, padding=1), nn.ReLU(),
            nn.AdaptiveAvgPool2d((7, 7))
        )

        self.head = nn.Conv2d(128, 5 + C, kernel_size=1)

    def forward(self, x):
        x = self.backbone(x)
        x = self.head(x)
        x = x.permute(0, 2, 3, 1)
        return x

if __name__ == '__main__':
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # 1. Load the Custom PyTorch Fire Detection Model
    print("Loading Custom PyTorch Fire Detection model...")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    model_path = os.path.join(current_dir, "Fire_Detection", "fire_detection_model.pt")
    
    try:
        model = FireDetectionModel(S=7, C=2).to(device)
        model.load_state_dict(torch.load(model_path, map_location=device))
        model.eval()
        print("Custom Fire Detection model loaded successfully.")
    except Exception as e:
        print(f"Error loading custom fire model: {e}")
        model = None

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

    # 1.1 Load the Keras Models for Raspberry Pi (Fall and Human)
    print("Loading Raspberry Pi Fall and Human Detection models...")
    fall_model_pi_path = os.path.join(current_dir, "Fall_Detection", "fall_detection_scratch.h5")
    human_model_pi_path = os.path.join(current_dir, "Human_Detection", "human.h5")
    
    try:
        fall_model_pi = tf.keras.models.load_model(fall_model_pi_path)
        human_model_pi = tf.keras.models.load_model(human_model_pi_path)
        print("Raspberry Pi models loaded successfully.")
    except Exception as e:
        print(f"Error loading Keras models: {e}")
        fall_model_pi, human_model_pi = None, None

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
        if pi_camera_url.startswith("tcp://"):
            print(f"Using TCPCameraStream for {pi_camera_url}...")
            cap_pi = TCPCameraStream(pi_camera_url).start()
        else:
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
            robot_z = T_matrix[2, 3] # Use Camera Z (depth) for Map Y
            
            # Calibrate start position on first valid detection to align map frame
            if robot_start_x is None:
                robot_start_x = robot_x
                robot_start_y = robot_z
                print(f"[CALIBRATION] Robot origin set to camera coordinates ({robot_start_x:.3f}, {robot_start_y:.3f})")
            
            robot_x_map = robot_x - robot_start_x
            robot_y_map = robot_z - robot_start_y

        # 3. Run Pre-trained YOLOv8 Fire Detection on the SAME Tapo frame
        fire_active = False # Flag to trigger downstream MQTT pipelines
        fire_x_target = None
        fire_y_target = None
        max_conf = 0.0
        frame_h, frame_w = display_frame_tapo.shape[:2]
        frame_area = float(frame_h * frame_w)
        floor_min_y = int(frame_h * 0.55)
        edge_margin_px = 20
        max_box_area_ratio = 0.12
        max_box_width_ratio = 0.35
        max_box_height_ratio = 0.45
        use_hsv_fire_fallback = True  # Re-enabled for testing with mobile screens
        
        # Custom PyTorch Model Inference
        custom_detections = []
        if model is not None:
            model.eval()
            img_rgb = cv2.cvtColor(display_frame_tapo, cv2.COLOR_BGR2RGB)
            img_input = cv2.resize(img_rgb, (416, 416)).transpose(2,0,1) / 255.0
            tensor = torch.tensor(img_input, dtype=torch.float32).unsqueeze(0).to(device)
            
            with torch.no_grad():
                out = model(tensor) # Shape: (1, 7, 7, 7)
                
            S = 7
            conf_map = torch.sigmoid(out[0, ..., 4])
            flat_idx = torch.argmax(conf_map)
            conf_val = conf_map.flatten()[flat_idx].item()
            
            if conf_val > 0.35:
                j = (flat_idx // S).item()
                i = (flat_idx % S).item()
                
                box = out[0, j, i, 0:4] # x_cell, y_cell, w, h
                
                # Convert to pixel coordinates
                x_abs = (box[0].item() + i) / S * frame_w
                y_abs = (box[1].item() + j) / S * frame_h
                w_abs = box[2].item() * frame_w
                h_abs = box[3].item() * frame_h
                
                x1 = int(x_abs - w_abs/2)
                y1 = int(y_abs - h_abs/2)
                x2 = int(x_abs + w_abs/2)
                y2 = int(y_abs + h_abs/2)
                
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(frame_w, x2), min(frame_h, y2)
                
                custom_detections.append({'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'conf': conf_val})
        
        hsv_detected = False
        hsv_x = None
        hsv_y = None

        if use_hsv_fire_fallback:
            # Optional color fallback, re-enabled for testing with mobile screens
            hsv = cv2.cvtColor(display_frame_tapo, cv2.COLOR_BGR2HSV)
            
            # Tuned for candle flames ONLY (orange-red, NOT golden yellow)
            # Golden KSIU logo on robot: H~25-35 (yellow) — excluded by H<=18 cutoff
            # Candle flame: H~0-18 (orange-red), S>=150 (very saturated), V>=200 (glowing)
            lower_flame1 = np.array([0, 150, 200], dtype=np.uint8)
            upper_flame1 = np.array([18, 255, 255], dtype=np.uint8)
            lower_flame2 = np.array([165, 150, 200], dtype=np.uint8)
            upper_flame2 = np.array([180, 255, 255], dtype=np.uint8)
            
            mask1 = cv2.inRange(hsv, lower_flame1, upper_flame1)
            mask2 = cv2.inRange(hsv, lower_flame2, upper_flame2)
            mask = cv2.bitwise_or(mask1, mask2)
            
            kernel = np.ones((5, 5), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            for contour in sorted(contours, key=cv2.contourArea, reverse=True):
                area = cv2.contourArea(contour)
                if area <= 50:
                    continue

                x1_hsv, y1_hsv, w_hsv, h_hsv = cv2.boundingRect(contour)
                x2_hsv = x1_hsv + w_hsv
                y2_hsv = y1_hsv + h_hsv
                area_ratio = area / frame_area

                # Verify the detected region is actually glowing bright (not just warm-colored)
                # Extract the V (brightness) channel values inside the contour bounding box
                roi_v = hsv[y1_hsv:y2_hsv, x1_hsv:x2_hsv, 2]  # V channel
                if roi_v.size == 0:
                    continue
                avg_brightness = float(np.mean(roi_v))
                if avg_brightness < 210:
                    # Not bright enough to be a flame — skip (floor tiles are ~120-180)
                    continue

                if area_ratio > 0.05:
                    continue
                if x1_hsv <= edge_margin_px or x2_hsv >= (frame_w - edge_margin_px):
                    continue
                
                if marker_center is not None:
                    u_center = (x1_hsv + x2_hsv) / 2.0
                    v_center = (y1_hsv + y2_hsv) / 2.0
                    dist_px = np.sqrt((u_center - marker_center[0])**2 + (v_center - marker_center[1])**2)
                    if dist_px < 400:
                        # Within robot body zone — skip (increased to 400 to cover the whole chassis)
                        continue
                
                # Flame shape check: candle flames are taller than wide, text/logos are wider
                if h_hsv < w_hsv * 0.8:
                    continue
                
                cv2.rectangle(display_frame_tapo, (x1_hsv, y1_hsv), (x2_hsv, y2_hsv), (0, 255, 0), 2)
                cv2.putText(display_frame_tapo, "Fire (HSV)", (x1_hsv, y1_hsv - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                
                hsv_center_x = (x1_hsv + x2_hsv) / 2.0
                hsv_center_y = y2_hsv
                
                hsv_detected = True
                hsv_x = hsv_center_x
                hsv_y = hsv_center_y
                break
        
        for det in custom_detections:
            conf = det['conf']
            
            # Extract bounding box pixel coordinates
            x1, y1, x2, y2 = det['x1'], det['y1'], det['x2'], det['y2']
                box_w = x2 - x1
                box_h = y2 - y1
                box_area_ratio = (box_w * box_h) / frame_area
                box_width_ratio = box_w / float(frame_w)
                box_height_ratio = box_h / float(frame_h)

                # Ignore giant detections, border-touching detections, and detections floating high in the image.
                if box_area_ratio > max_box_area_ratio:
                    continue
                if box_width_ratio > max_box_width_ratio or box_height_ratio > max_box_height_ratio:
                    continue
                if x1 <= edge_margin_px or x2 >= (frame_w - edge_margin_px):
                    continue

                # 2D PIXEL FILTER: Ignore if it overlaps with the robot's ArUco marker
                # Reduced to 80px to allow candle detection near the robot
                if marker_center is not None:
                    u_fire_center = (x1 + x2) / 2.0
                    v_fire_center = (y1 + y2) / 2.0
                    dist_px = np.sqrt((u_fire_center - marker_center[0])**2 + (v_fire_center - marker_center[1])**2)
                    if dist_px < 80:
                        continue

                if conf > max_conf:
                    # Draw bounding box for operator visibility (always, even without ArUco)
                    cv2.rectangle(display_frame_tapo, (x1, y1), (x2, y2), (0, 0, 255), 3)
                    label = f"Fire AI: {conf:.2f}"
                    cv2.putText(display_frame_tapo, label, (x1, y1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

                    fire_active = True
                    last_fire_detect_time = current_time
                    max_conf = conf

                    # Only calculate navigation target if ArUco tracking is active
                    if T_matrix is not None and robot_start_x is not None:
                        # Calculate pixel center of the fire base (where it touches the floor)
                        u_fire = (x1 + x2) / 2.0
                        v_fire = y2
                        
                        # Pinhole projection mapping to camera coordinate space
                        z_floor = T_matrix[2, 3]
                        fx = placeholder_camera_matrix[0, 0]
                        fy = placeholder_camera_matrix[1, 1]
                        cx = placeholder_camera_matrix[0, 2]
                        cy = placeholder_camera_matrix[1, 2]
                        
                        x_fire_cam = ((u_fire - cx) * z_floor) / fx
                        
                        fire_x_target = x_fire_cam - robot_start_x
                        fire_y_target = 0.0 # Force robot to drive straight toward X

                        # 3D Map-Space Filter: Ignore targets too close to robot
                        dist_to_start = np.sqrt(fire_x_target**2 + fire_y_target**2)
                        dist_to_robot = 999.0
                        if robot_x_map is not None and robot_y_map is not None:
                            dist_to_robot = np.sqrt((fire_x_target - robot_x_map)**2 + (fire_y_target - robot_y_map)**2)
                        
                        if dist_to_start >= 0.15 and dist_to_robot >= 0.15:
                            # Latch target coordinate in memory
                            latched_fire_x = fire_x_target
                            latched_fire_y = fire_y_target
                            latched_fire_active = True
        
        # ==================== FALLBACK TO HSV DETECTION IF YOLO FOUND NOTHING ====================
        if not fire_active and hsv_detected and hsv_x is not None and hsv_y is not None:
            # HSV detected a candle flame — always report fire status to operator
            fire_active = True
            last_fire_detect_time = current_time
            max_conf = 0.5  # Give HSV detection a default confidence

            # Only calculate navigation target if ArUco tracking is active
            if T_matrix is not None and robot_start_x is not None:
                # Convert HSV pixel coordinates to 3D space using pinhole projection
                z_floor = T_matrix[2, 3]
                fx = placeholder_camera_matrix[0, 0]
                fy = placeholder_camera_matrix[1, 1]
                cx = placeholder_camera_matrix[0, 2]
                cy = placeholder_camera_matrix[1, 2]
                
                x_fire_cam = ((hsv_x - cx) * z_floor) / fx
                fire_x_target = x_fire_cam - robot_start_x
                fire_y_target = 0.0 # Force robot to drive straight toward X
                
                # Apply 3D distance filter
                dist_to_start = np.sqrt(fire_x_target**2 + fire_y_target**2)
                dist_to_robot = 999.0
                if robot_x_map is not None and robot_y_map is not None:
                    dist_to_robot = np.sqrt((fire_x_target - robot_x_map)**2 + (fire_y_target - robot_y_map)**2)
                
                if dist_to_start >= 0.15 and dist_to_robot >= 0.15:
                    # Latch the HSV detection
                    latched_fire_x = fire_x_target
                    latched_fire_y = fire_y_target
                    latched_fire_active = True

        # 3.2 Latch override and arrival check
        if latched_fire_active:
            # If we haven't seen any fire in the scene for 15 seconds, clear the latch
            # Increased from 5.0 to 15.0 for better reliability
            if current_time - last_fire_detect_time > 15.0:
                print(f"[LATCH TIMEOUT] No fire detected for 15.0 seconds. Clearing latched target.")
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
                d_safe = 0.3  # Reduced from 0.8m to 0.3m (30cm away) to get closer to the candle
                dx = latched_fire_x - robot_x_map
                dy = latched_fire_y - robot_y_map
                d_total = np.sqrt(dx**2 + dy**2)
                
                # Keep latch active so robot stays at target, let you control pump/nozzle manually
                # (No automatic latch clear - keep target active)

        # 3.5 Throttle MQTT messages and goal updates (every 2 seconds)
        if current_time - last_goal_time > 2.0:
            fire_payload = {
                "fire": fire_active,
                "confidence": round(max_conf, 2),
                "class": "flame" if fire_active else "none"
            }
            try:
                mqtt_client.publish("robot/fire_detected", json.dumps(fire_payload))
            except Exception as e:
                print(f"MQTT publish error (fire_detected): {e}")

            if fire_active and fire_x_target is not None and fire_y_target is not None:
                if T_matrix is None:
                    print("[NAV HOLD] Robot marker lost. Navigation target not published.")
                else:
                    d_safe = 0.3  # Stop 30cm away from candle (reduced from 80cm)
                    dx = fire_x_target - robot_x_map
                    dy = fire_y_target - robot_y_map
                    d_total = np.sqrt(dx**2 + dy**2)
                    
                    if d_total > d_safe:
                        x_nav = fire_x_target - (d_safe * dx / d_total)
                        y_nav = fire_y_target - (d_safe * dy / d_total)
                        yaw_nav = math.atan2(dy, dx) + math.pi
                        
                        nav_payload = {
                            "x": round(float(x_nav), 3),
                            "y": round(float(y_nav), 3),
                            "yaw": round(float(yaw_nav), 3)
                        }
                        try:
                            mqtt_client.publish("ambers/robot/navigation/target", json.dumps(nav_payload))
                            print(f"[AUTONOMOUS TARGET] Fire target active! Safe Goal: x={x_nav:.3f}, y={y_nav:.3f} (Distance left: {d_total:.3f}m)")
                        except Exception as e:
                            print(f"MQTT publish error (navigation target): {e}")
                    else:
                        print(f"[TARGET REACHED] Robot within safe distance ({d_total:.3f}m <= {d_safe}m). Use web UI to control pump/nozzle!")
            
            last_goal_time = current_time

        # 4. Run Raspberry Pi Fall & Human Detection (Keras) on the Pi Camera frame
        display_frame_pi = None
        if ret_pi and frame_pi is not None:
            display_frame_pi = frame_pi.copy()
            
            if fall_model_pi is not None and human_model_pi is not None:
                fall_img_size = 224
                human_img_size = 128
                
                # Preprocess for Fall model
                fall_pi_img = cv2.resize(frame_pi, (fall_img_size, fall_img_size))
                fall_pi_img = cv2.cvtColor(fall_pi_img, cv2.COLOR_BGR2RGB)
                fall_pi_img = fall_pi_img.astype(np.float32) / 255.0
                fall_pi_input = np.expand_dims(fall_pi_img, axis=0)
                
                # Using model(inputs, training=False) is much faster than model.predict for single frames
                fall_pi_pred = float(fall_model_pi(fall_pi_input, training=False)[0][0])
                
                # Preprocess for Human model
                human_pi_img = cv2.resize(frame_pi, (human_img_size, human_img_size))
                human_pi_img = cv2.cvtColor(human_pi_img, cv2.COLOR_BGR2RGB)
                human_pi_img = human_pi_img.astype(np.float32)
                human_pi_input = np.expand_dims(human_pi_img, axis=0)
                
                # Using model(inputs, training=False) is much faster than model.predict for single frames
                human_pi_pred = float(human_model_pi(human_pi_input, training=False)[0][0])
                
                # Draw labels for Keras models
                font = cv2.FONT_HERSHEY_SIMPLEX
                cv2.putText(display_frame_pi, f"Pi Fall: {fall_pi_pred:.2f}", (10, 30), font, 0.8, (0, 0, 255) if fall_pi_pred > 0.5 else (0, 255, 0), 2)
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
