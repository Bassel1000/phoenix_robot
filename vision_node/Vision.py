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


class MiniYOLO(nn.Module):
    def __init__(self, S=7, C=2):
        super().__init__()
        self.S = S
        self.C = C

        self.backbone = nn.Sequential(
            nn.Conv2d(3,16,3,padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(16,32,3,padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(32,64,3,padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(64,128,3,padding=1), nn.ReLU(),
            nn.AdaptiveAvgPool2d((7,7))
        )

        self.head = nn.Conv2d(128, 5+2, kernel_size=1)

    def forward(self, x):
        x = self.backbone(x)
        x = self.head(x)
        x = x.permute(0,2,3,1)
        return x

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

    if ids is not None:
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

    return transformation_matrix, image_frame

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
    # 1. Load the Custom Fire Detection Model (MiniYOLO)
    print("Loading Custom Fire Detection model...")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = MiniYOLO(S=7, C=2).to(device)
    
    # Construct the absolute path to the model file to avoid FileNotFoundError
    current_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(current_dir, "Fire_Detection_TapoC210", "fire_detection_model.pt")
    
    # Load the state dict.
    model.load_state_dict(torch.load(model_path, map_location=device))
    model.eval()

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

    # Initialize cameras
    # Provide the RTSP URL via environment variable or place it directly below 
    tapo_rtsp_url = os.environ.get("RTSP_URL") 
    cap_tapo = CameraStream(tapo_rtsp_url).start()

    if not cap_tapo.isOpened():
        print(f"Failed to open video stream. Input used: {tapo_rtsp_url}")
        exit(1)

    # Initialize Raspberry Pi Camera Module 3 stream
    # Since this runs on the laptop, the Pi must stream its camera over the network (e.g., via RTSP, HTTP, UDP, TCP).
    # To stream with MAX FOV from a Pi Camera Module 3 (avoiding center-crop), run this command on the Raspberry Pi:
    # sudo rpicam-vid -n -t 0 --mode 4608:2592:12 --width 640 --height 360 --framerate 30 --codec mjpeg --listen -o tcp://0.0.0.0:8888
    # Then in your laptop's .env file set: PI_CAMERA_URL="tcp://<PI_IP>:8888"
    pi_camera_url = os.environ.get("PI_CAMERA_URL")
    if pi_camera_url:
        cap_pi = CameraStream(pi_camera_url).start()
    else:
        print("PI_CAMERA_URL not set in .env. Falling back to the laptop webcam (0) for testing the Pi models.")
        cap_pi = CameraStream(0).start()

    if not cap_pi.isOpened():
        print("Failed to open Raspberry Pi Camera stream. Models will skip Pi frames.")

    # Placeholder camera matrix
    placeholder_camera_matrix = np.array([[800, 0, 320], [0, 800, 240], [0, 0, 1]], dtype=np.float32)
    placeholder_dist_coeffs = np.zeros((4,1))

    print("Starting Robot Tracking and Fire Detection...")

    while True:
        # Get latest frames from background threads completely instantly and without blocking
        ret_tapo, frame_tapo = cap_tapo.read()
        ret_pi, frame_pi = False, None
        
        if cap_pi.isOpened():
            ret_pi, frame_pi = cap_pi.read()
            
        if not ret_tapo or frame_tapo is None:
            time.sleep(0.01) # Avoid 100% CPU lock while stream connects or reconnects
            continue

        # 2. Run ArUco tracking for the robot (Kinematics) on Tapo
        T_matrix, display_frame_tapo = calculate_transformation_matrix(
            frame_tapo, 
            placeholder_camera_matrix, 
            placeholder_dist_coeffs, 
            marker_length=0.093
        )

        if T_matrix is not None:
            # We found the robot!
            robot_x = T_matrix[0, 3]
            robot_y = T_matrix[1, 3]
            # print(f"Robot Location: X:{robot_x:.2f}, Y:{robot_y:.2f}")

        # 3. Run Custom Fire Detection on the SAME Tapo frame
        # Preprocess
        img_rgb = cv2.cvtColor(display_frame_tapo, cv2.COLOR_BGR2RGB)
        h_orig, w_orig = display_frame_tapo.shape[:2]
        
        # Resize to 416x416, Swap axes (HWC to CHW), and normalize (0-1)
        img_input = cv2.resize(img_rgb, (416, 416)).transpose(2, 0, 1) / 255.0
        tensor = torch.tensor(img_input, dtype=torch.float32).unsqueeze(0).to(device)
        
        with torch.no_grad():
            out = model(tensor) # Shape: (1, 7, 7, 7)
            
        # Parse output for the single highest confidence prediction
        S = 7
        conf_map = out[0, ..., 4]
        flat_idx = torch.argmax(conf_map)
        j, i = torch.unravel_index(flat_idx, (S, S))
        
        conf = conf_map[j, i].item()
        
        fire_active = False # Flag you can use to trigger MQTT
        
        if conf > 0.50: # Only show detections with > 50% confidence
            # Get prediction data
            box = out[0, j, i, 0:4] # x_cell, y_cell, w, h
            cls = torch.argmax(out[0, j, i, 5:]).item()
            
            # Convert back to original pixel coordinates
            x_abs = ((box[0] + i) / S * w_orig).item()
            y_abs = ((box[1] + j) / S * h_orig).item()
            w_abs = (box[2] * w_orig).item()
            h_abs = (box[3] * h_orig).item()
            
            # Bounding box corners
            x1 = int(x_abs - w_abs / 2)
            y1 = int(y_abs - h_abs / 2)
            x2 = int(x_abs + w_abs / 2)
            y2 = int(y_abs + h_abs / 2)
            
            # Checking if the class detected represents fire (assuming 0 or 1 is fire dependening on the labels)
            if cls == 0 or cls == 1: 
                fire_active = True
                
                # Draw a red bounding box around the fire
                cv2.rectangle(display_frame_tapo, (x1, y1), (x2, y2), (0, 0, 255), 3)
                
                # Add label and confidence score
                label = f"Fire: {conf:.2f}"
                cv2.putText(display_frame_tapo, label, (x1, y1 - 10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

        # 4. Run Raspberry Pi Fire & Human Detection (Keras) on the Pi Camera frame
        display_frame_pi = None
        if ret_pi and frame_pi is not None and fire_model_pi is not None and human_model_pi is not None:
            display_frame_pi = frame_pi.copy()
            img_size = 128
            
            # Preprocess for Fire model (requires manual scaling)
            fire_pi_img = cv2.resize(frame_pi, (img_size, img_size))
            fire_pi_img = cv2.cvtColor(fire_pi_img, cv2.COLOR_BGR2RGB)
            fire_pi_img = fire_pi_img.astype(np.float32) / 255.0
            fire_pi_input = np.expand_dims(fire_pi_img, axis=0)
            
            fire_pi_pred = fire_model_pi.predict(fire_pi_input, verbose=0)[0][0]
            
            # Preprocess for Human model (rescaling layer is inside the model)
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

        # Press 'q' to quit
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap_tapo.stop()
    if cap_pi.isOpened():
        cap_pi.stop()
    cv2.destroyAllWindows()