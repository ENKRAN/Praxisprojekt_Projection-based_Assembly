from pupil_apriltags import Detector
from typing import Any

class AprilTagDetector:
    """
    Class to detect apriltags in a grayscale frame
    """
    def __init__(self, tag_family="tagStandard41h12", fx=None, fy=None, cx=None, cy=None, tag_size=0.075) -> None:
        """
        Initialize the AprilTag detector

        :param tag_family: Tag family to detect
        :param fx: Focal length in x-direction
        :param fy: Focal length in y-direction
        :param cx: Principal point in x-direction
        :param cy: Principal point in y-direction
        :param tag_size: Size of the apriltag in meters
        """
        self.detector = Detector(families=tag_family)
        self.fx = fx
        self.fy = fy
        self.cx = cx
        self.cy = cy
        self.tag_size = tag_size

    def detect(self, gray_frame) -> Any:
        """
        Detect apriltags in a grayscale frame

        :param gray_frame: Grayscale frame to detect apriltags in
        :return: List of apriltags detected in the frame
        """
        # Detect apriltags in the frame
        results = self.detector.detect(gray_frame, estimate_tag_pose=True, 
                                       camera_params=[self.fx, self.fy, self.cx, self.cy], 
                                       tag_size=self.tag_size)
        return results
    