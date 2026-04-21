# Contributor: Bassel Elbahnasy
import os
import cv2
import numpy as np

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
    # 1. Load the YOLO Fire Detection Model
    # Note: Point this to your actual model file (e.g., mini_yolo_model.pt)
    print("Loading YOLO Fire Detection model...")
    model = YOLO("mini_yolo_model.pt") # Update with the correct path to your .pt file

    # Initialize camera
    tapo_rtsp_url = os.environ.get("RTSP_URL", "rtsp://default_user:default_pass@127.0.0.1:554/stream1")
    cap = cv2.VideoCapture(tapo_rtsp_url)

    # Placeholder camera matrix
    placeholder_camera_matrix = np.array([[800, 0, 320], [0, 800, 240], [0, 0, 1]], dtype=np.float32)
    placeholder_dist_coeffs = np.zeros((4,1))

    print("Starting Robot Tracking and Fire Detection...")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

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

        # 3. Run YOLO Fire Detection on the SAME frame
        results = model(display_frame, stream=True, verbose=False)

        fire_active = False # Flag you can use to trigger MQTT
        
        for r in results:
            boxes = r.boxes
            for box in boxes:
                # Get bounding box coordinates
                x1, y1, x2, y2 = int(box.xyxy[0][0]), int(box.xyxy[0][1]), int(box.xyxy[0][2]), int(box.xyxy[0][3])
                
                # Get Confidence and Class
                conf = float(box.conf[0])
                cls = int(box.cls[0])

                # Assuming class 0 is 'Fire' (adjust if your model uses a different class ID)
                if conf > 0.50: # Only show detections with > 50% confidence
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