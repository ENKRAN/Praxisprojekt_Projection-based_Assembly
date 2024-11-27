from .camera import Camera
from .apriltag_detection import AprilTagDetector
import numpy as np
from typing import Tuple, Optional, Dict
import cv2

def initialize_system(depth_intrinsics: bool = False) -> Tuple[Camera, AprilTagDetector, np.ndarray, Dict[str, float], Optional[Dict[str, float]]]:
    camera = Camera(640, 480, 640, 480, 60)
    color_intrinsics = camera.get_color_sensor_intrinsics()

    if depth_intrinsics:
        depth_intrinsics = camera.get_depth_sensor_intrinsics()

    apriltag_detector = AprilTagDetector(fx=color_intrinsics["fx"], fy=color_intrinsics["fy"],
                                         cx=color_intrinsics["ppx"], cy=color_intrinsics["ppy"])
    camera_matrix = np.array([[apriltag_detector.fx, 0, apriltag_detector.cx],
                              [0, apriltag_detector.fy, apriltag_detector.cy],
                              [0, 0, 1]])
    return camera, apriltag_detector, camera_matrix, color_intrinsics, depth_intrinsics

def get_calibration_data(calibration_data_path):
    fs = cv2.FileStorage(calibration_data_path, cv2.FILE_STORAGE_READ)

    # Kameraparameter
    cam_K = fs.getNode('camK').mat()
    cam_kc = fs.getNode('camKc').mat()

    # Projektorparameter
    proj_K = fs.getNode('prjK').mat()
    proj_kc = fs.getNode('prjKc').mat()

    # Rotations- und Translationsvektoren
    R = fs.getNode('R').mat()
    T = fs.getNode('T').mat()

    fs.release()

    if cam_K is None or cam_kc is None or proj_K is None or proj_kc is None or R is None or T is None:
        print('Kalibrierungsdaten konnten nicht geladen werden.')
        exit()
        
    return cam_K, cam_kc, proj_K, proj_kc, R, T