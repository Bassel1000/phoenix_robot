# Contributor: Bassel Elbahnasy
import os
import cv2
import numpy as np
import torch
import torch.nn as nn
from dotenv import load_dotenv

# Load environment variables from a .env file if present
load_dotenv()

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

if __name__ == '__main__':
    # 1. Load the Custom Fire Detection Model (MiniYOLO)
    print("Loading Custom Fire Detection model...")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = MiniYOLO(S=7, C=2).to(device)
    
    # Construct the absolute path to the model file to avoid FileNotFoundError
    current_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(current_dir, "fire_detection_model.pt")
    
    # Load the state dict.
    model.load_state_dict(torch.load(model_path, map_location=device))
    model.eval()

    # Initialize camera
    # Provide the RTSP URL via environment variable or place it directly below 
    tapo_rtsp_url = os.environ.get("RTSP_URL") 
    cap = cv2.VideoCapture(tapo_rtsp_url)
    
    # Reduce OpenCV buffer size so we don't process old cached frames, which causes lag
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    if not cap.isOpened():
        print(f"Failed to open video stream. Input used: {tapo_rtsp_url}")
        exit(1)

    # Placeholder camera matrix
    placeholder_camera_matrix = np.array([[800, 0, 320], [0, 800, 240], [0, 0, 1]], dtype=np.float32)
    placeholder_dist_coeffs = np.zeros((4,1))

    print("Starting Robot Tracking and Fire Detection...")

    while True:
        # Grab frames continuously but only decode the most recent one to prevent buffer buildup and lag
        cap.grab()
        ret, frame = cap.retrieve()
        if not ret:
            continue

        # 2. Run ArUco tracking for the robot (Kinematics)
        T_matrix, display_frame = calculate_transformation_matrix(
            frame, 
            placeholder_camera_matrix, 
            placeholder_dist_coeffs, 
            marker_length=0.093
        )

        if T_matrix is not None:
            # We found the robot!
            robot_x = T_matrix[0, 3]
            robot_y = T_matrix[1, 3]
            # print(f"Robot Location: X:{robot_x:.2f}, Y:{robot_y:.2f}")

        # 3. Run Custom Fire Detection on the SAME frame
        # Preprocess
        img_rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
        h_orig, w_orig = display_frame.shape[:2]
        
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
                cv2.rectangle(display_frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
                
                # Add label and confidence score
                label = f"Fire: {conf:.2f}"
                cv2.putText(display_frame, label, (x1, y1 - 10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

        # --- Display the Window ---
        cv2.namedWindow('Vision Node: Tracking & AI', cv2.WINDOW_NORMAL)
        cv2.resizeWindow('Vision Node: Tracking & AI', 1280, 720)
        cv2.imshow('Vision Node: Tracking & AI', display_frame)

        # Press 'q' to quit
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()