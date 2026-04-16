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

# --- Example Usage ---
if __name__ == '__main__':
    # Initialize webcam
    # Provide the RTSP URL via the RTSP_URL environment variable to avoid hardcoded credentials
    # tapo_rtsp_url = os.environ.get("RTSP_URL", "rtsp://default_user:default_pass@127.0.0.1:554/stream1")
    cap = cv2.VideoCapture(0)

    # NOTE: You MUST calibrate your specific camera to get accurate matrices. 
    # These are placeholder intrinsic parameters for a generic 720p webcam.
    placeholder_camera_matrix = np.array([[800, 0, 320], [0, 800, 240], [0, 0, 1]], dtype=np.float32)
    placeholder_dist_coeffs = np.zeros((4,1))

    print("Looking for ArUco marker...")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Calculate the T_matrix
        T_matrix, display_frame = calculate_transformation_matrix(
            frame, 
            placeholder_camera_matrix, 
            placeholder_dist_coeffs, 
            marker_length=0.093 # 10 cm printed marker
        )

        if T_matrix is not None:
            print("\nTransformation Matrix (Camera to Robot):")
            print(np.round(T_matrix, decimals=3))

        # --- NEW CODE ADDED HERE ---
        # Create a resizable window
        cv2.namedWindow('Robot Tracking', cv2.WINDOW_NORMAL)
        # Resize the window to fit comfortably on your screen (e.g., 1280x720)
        cv2.resizeWindow('Robot Tracking', 1280, 720)
        # ---------------------------

        # Show the video feed with the drawn axis
        cv2.imshow('Robot Tracking', display_frame)

        # Press 'q' to quit
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()