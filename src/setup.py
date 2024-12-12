from .camera import Camera
from .apriltag_detection import AprilTagDetector
import numpy as np
from typing import Tuple, Optional, Dict
import cv2
import time
from screeninfo import get_monitors
import sys

def initialize_system(color_width=640, color_height=480, depth_width=640, depth_heigth=480, fps=60, depth_intrinsics: bool = False) -> Tuple[Camera, AprilTagDetector, np.ndarray, Dict[str, float], Optional[Dict[str, float]]]:
    """
    Initializes the camera and AprilTag detector.

    :param depth_intrinsics: Whether to get the depth sensor intrinsics
    :return: The camera, AprilTag detector, camera matrix, color intrinsics, and depth intrinsics
    """
    # Initialize the camera and AprilTag detector
    camera = Camera(color_width, color_height, depth_width, depth_heigth, fps)
    color_intrinsics = camera.get_color_sensor_intrinsics()

    if depth_intrinsics:
        depth_intrinsics = camera.get_depth_sensor_intrinsics()

    apriltag_detector = AprilTagDetector(fx=color_intrinsics["fx"], fy=color_intrinsics["fy"],
                                         cx=color_intrinsics["ppx"], cy=color_intrinsics["ppy"])
    
    camera_matrix = np.array([[apriltag_detector.fx, 0, apriltag_detector.cx],
                              [0, apriltag_detector.fy, apriltag_detector.cy],
                              [0, 0, 1]])
    
    return camera, apriltag_detector, camera_matrix, color_intrinsics, depth_intrinsics

def get_calibration_data(calibration_data_path) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Loads the camera and projector calibration data from the calibration.yml file.

    :param calibration_data_path: Path to the calibration.yml file
    :return: Camera matrix, distortion coefficients, projector matrix, projector distortion coefficients, rotation matrix, and translation vector
    """
    # Load the file
    fs = cv2.FileStorage(calibration_data_path, cv2.FILE_STORAGE_READ)

    # Camera parameter
    cam_K = fs.getNode('camK').mat()
    cam_kc = fs.getNode('camKc').mat()

    # Projector parameter
    proj_K = fs.getNode('prjK').mat()
    proj_kc = fs.getNode('prjKc').mat()

    # Rotation and translation
    R = fs.getNode('R').mat()
    T = fs.getNode('T').mat()

    fs.release()

    if cam_K is None or cam_kc is None or proj_K is None or proj_kc is None or R is None or T is None:
        print("Error: Calibration data could not be loaded. Please check the file path.")
        exit()
        
    return cam_K, cam_kc, proj_K, proj_kc, R, T

def update_windows(projector_window_name) -> None:
    """
    Update the windows in a separate thread so that the windows do not freeze or interfere with each other.

    :param projector_window_name: The name of the projector window
    """
    while True:
        if cv2.getWindowProperty('AprilTag Projection Mapping', cv2.WND_PROP_VISIBLE) < 1 and \
           cv2.getWindowProperty(projector_window_name, cv2.WND_PROP_VISIBLE) < 1:
             break
        cv2.waitKey(1)
        time.sleep(0.01)
