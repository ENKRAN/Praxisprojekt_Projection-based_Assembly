from .camera import Camera
from .apriltag_detection import AprilTagDetector
import numpy as np
from typing import Tuple, Optional, Dict

def initialize_system(depth_intrinsics: bool = False) -> Tuple[Camera, AprilTagDetector, np.ndarray, Dict[str, float], Optional[Dict[str, float]]]:
    camera = Camera(1280, 720, 1280, 720, 30)
    color_intrinsics = camera.get_color_sensor_intrinsics()

    if depth_intrinsics:
        depth_intrinsics = camera.get_depth_sensor_intrinsics()

    apriltag_detector = AprilTagDetector(fx=color_intrinsics["fx"], fy=color_intrinsics["fy"],
                                         cx=color_intrinsics["ppx"], cy=color_intrinsics["ppy"])
    camera_matrix = np.array([[apriltag_detector.fx, 0, apriltag_detector.cx],
                              [0, apriltag_detector.fy, apriltag_detector.cy],
                              [0, 0, 1]])
    return camera, apriltag_detector, camera_matrix, color_intrinsics, depth_intrinsics