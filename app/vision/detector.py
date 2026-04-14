from pupil_apriltags import Detector
import numpy as np
from typing import List, Any
from app.core.user_settings import UserSettings

class AprilTagDetector:
    def __init__(self, camera_intrinsics: np.ndarray, tag_family: str = "tagStandard41h12", tag_size: float = None):
        self.detector = Detector(families=tag_family)
        
        self.fx = camera_intrinsics[0, 0]
        self.fy = camera_intrinsics[1, 1]
        self.cx = camera_intrinsics[0, 2]
        self.cy = camera_intrinsics[1, 2]
        self.tag_size = tag_size if tag_size is not None else UserSettings.get_tag_size()

    def detect(self, gray_frame: np.ndarray) -> List[Any]:
        results = self.detector.detect(
            gray_frame, 
            estimate_tag_pose=True, 
            camera_params=[self.fx, self.fy, self.cx, self.cy], 
            tag_size=self.tag_size
        )
        return results