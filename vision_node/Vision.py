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
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # 1. Load the Pre-trained YOLOv8 Fire Detection Model
    print("Loading Pretrained YOLOv8 Fire Detection model...")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    # Securely fetch model from Hugging Face cache using huggingface_hub helper
    from huggingface_hub import hf_hub_download
    try:
        print("Downloading custom fire detection weights from Hugging Face Hub...")
        # Downloads 'best.pt' from a highly accurate fire-smoke dataset finetune
        model_path = hf_hub_download(repo_id="rabahdev/fire-smoke-yolov8n", filename="best.pt")
        model = YOLO(model_path)
        print("Pretrained fire model initialized successfully.")
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

    # Placeholder camera matrix
    placeholder_camera_matrix = np.array([[800, 0, 320], [0, 800, 240], [0, 0, 1]], dtype=np.float32)
    placeholder_dist_coeffs = np.zeros((4,1))

    print("Starting Robot Tracking and Fire Detection...")

    while True:
        # Get latest frames instantly
        ret_tapo, frame_tapo = cap_tapo.read()
        ret_pi, frame_pi = False, None
        
        if cap_pi.isOpened():
            ret_pi, frame_pi = cap_pi.read()
            
        if not ret_tapo or frame_tapo is None:
            time.sleep(0.01) 
            continue

        # 2. Run ArUco tracking for the robot kinematics on Tapo
        T_matrix, display_frame_tapo = calculate_transformation_matrix(
            frame_tapo, 
            placeholder_camera_matrix, 
            placeholder_dist_coeffs, 
            marker_length=0.093
        )

        if T_matrix is not None:
            robot_x = T_matrix[0, 3]
            robot_y = T_matrix[1, 3]

        # 3. Run Pre-trained YOLOv8 Fire Detection on the SAME Tapo frame
        fire_active = False # Flag to trigger downstream MQTT pipelines
        
        # Pass the frame directly to YOLOv8
        results = model(display_frame_tapo, conf=0.60, verbose=False, device=device.type) 

        for r in results:
            boxes = r.boxes
            for box in boxes:
                conf = float(box.conf[0])
                cls = int(box.cls[0])

                # Extract bounding box pixel coordinates
                x1, y1, x2, y2 = map(int, box.xyxy[0])

                # Draw a red bounding box around the validated fire/smoke target
                cv2.rectangle(display_frame_tapo, (x1, y1), (x2, y2), (0, 0, 255), 3)
                
                # Overlay label metrics
                label = f"Fire AI: {conf:.2f}"
                cv2.putText(display_frame_tapo, label, (x1, y1 - 10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

                fire_active = True

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