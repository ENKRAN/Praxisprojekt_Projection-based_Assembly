from pupil_apriltags import Detector
from typing import List

class AprilTagDetector:
    """
    Class to detect apriltags in a grayscale frame
    """
    def __init__(self, tag_family="tagStandard41h12", fx=None, fy=None, cx=None, cy=None, tag_size=0.04) -> None:
        self.detector = Detector(families=tag_family)
        self.fx = fx
        self.fy = fy
        self.cx = cx
        self.cy = cy
        self.tag_size = tag_size

    def detect(self, gray_frame) -> List:
        """
        Detect apriltags in a grayscale frame

        :param gray_frame: Grayscale frame to detect apriltags in
        :return: List of apriltag detections
        """
        # Detect apriltags in the frame
        results = self.detector.detect(gray_frame, estimate_tag_pose=True, 
                                       camera_params=[self.fx, self.fy, self.cx, self.cy], 
                                       tag_size=self.tag_size)
        return results
